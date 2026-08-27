import logging
import secrets
import shutil
import uuid
from pathlib import Path

import sentry_sdk

from src.config import settings
from src.core.crypto import decrypt
from src.core.exceptions import BadRequestError, ConflictError, NotFoundError, PaymentRequiredError
from src.models.bot import Bot
from src.models.user import User
from src.repositories.api_keys_repository import ApiKeysRepository
from src.repositories.bot_repository import BotRepository
from src.schemas.bot import BotCreate
from src.services import docker_manager, freqtrade_client
from src.services.balance_guard import cannot_create_message, cannot_start_message, is_balance_sufficient
from src.services.bot_file_manager import BotFileManager
from src.services.strategy_presets import resolve_filters

logger = logging.getLogger(__name__)


class BotService:
    def __init__(self, bot_repo: BotRepository, api_keys_repo: ApiKeysRepository):
        self.bot_repo: BotRepository = bot_repo
        self.api_keys_repo: ApiKeysRepository = api_keys_repo

    # Процент, заданный пользователем, — это движение ЦЕНЫ, и плечо на него не влияет:
    # «take profit 1.5%» значит «цена прошла 1.5%», при любом плече. freqtrade же меряет
    # и minimal_roi, и stoploss в долях МАРЖИ, а маржа в leverage раз меньше позиции.
    # Поэтому здесь и только здесь процент цены умножается на плечо.
    #
    # Раньше умножения не было, и «1.5%» уезжало в freqtrade как 1.5% маржи — при x10
    # это 0.15% движения цены, в десять раз ближе, чем ожидал пользователь, и внутри
    # спреда. Заодно плечо переставало быть просто множителем результата: оно молча
    # меняло и цель, и стоп.

    @staticmethod
    def _build_take_profit(percent: float, leverage: int) -> dict:
        """Превращает 1.5 (процентов движения цены) при плече 10 в minimal_roi {"0": 0.15}."""
        return {"0": round(percent / 100.0 * leverage, 6)}

    @staticmethod
    def _build_stoploss(enabled: bool, percent: float | None, leverage: int) -> float:
        """
        Возвращает stoploss в формате freqtrade — отрицательная доля маржи.

        percent — движение цены в процентах, как его задал пользователь; на долю маржи
        его переводит плечо. Если SL выключен — кладём -0.99: позиция держится почти до
        полной потери маржи, то есть фактически до ликвидации.

        Верхнюю границу (percent * leverage < 100) проверяет схема BotCreate: стоп в целую
        маржу или дальше — это stoploss <= -1, такого freqtrade не принимает.
        """
        if not enabled or percent is None:
            return -0.99
        return -round(percent / 100.0 * leverage, 6)

    # Один биржевой ключ + одна пара = одна позиция на бирже: Bybit нетит сделки разных
    # ботов в неё же. Вход второго бота увеличит позицию первого, а стоп первого закроет
    # её целиком, вместе с чужой частью. Общей картины при этом нет ни у кого: у каждого
    # бота свой tradesv3.sqlite, и комиссия сервиса считается с разъехавшихся цифр.
    # Отсюда запрет — и на создании, и на запуске.
    #
    # Статусы проверяются разные по разным причинам, см. вызовы ниже.

    async def _ensure_pair_is_free(
        self,
        *,
        api_key_id: int,
        pair: str,
        statuses: tuple[str, ...] | None,
        exclude_bot_id: str | None,
        user_id: int,
        message: str,
    ) -> None:
        """Поднимает ConflictError, если на этом ключе уже есть боевой бот на этой паре."""
        # rival - соперник
        rival = await self.bot_repo.get_live_bot_on_pair(
            api_key_id,
            pair,
            statuses=statuses,
            exclude_bot_id=exclude_bot_id,
        )
        if rival is None:
            return

        logger.warning(
            "Bot rejected: another live bot already trades this pair on the same API key",
            extra={
                "user_id": user_id,
                "api_key_id": api_key_id,
                "pair": pair,
                "rival_bot_id": rival.id,
                "rival_status": rival.status,
            },
        )
        raise ConflictError(message.format(name=rival.name, pair=rival.pair))

    @staticmethod
    def _bot_dir(bot_id: str) -> Path:
        return settings.BOTS_DATA_DIR / bot_id

    async def create_bot(self, current_user: User, body: BotCreate):
        """
        Создаем папку бота, делаем запись в бд
        """
        # Боевой бот работает за комиссию с сервисного баланса, поэтому ниже порога
        # новые боты не создаются. Dry-run не трогаем: за него комиссия не берётся.
        # Проверка стоит первой — нет смысла занимать порт и писать строку в БД.
        if not body.dry_run and not is_balance_sufficient(current_user):
            logger.warning(
                "Bot creation rejected: service balance below minimum",
                extra={
                    "user_id": current_user.id,
                    "service_balance": current_user.service_balance,
                    "min_balance": settings.MIN_SERVICE_BALANCE_RUB,
                },
            )
            raise PaymentRequiredError(cannot_create_message())

        bot_id = str(uuid.uuid4())
        sentry_sdk.set_tag("bot_id", bot_id)
        sentry_sdk.set_tag("user_id", str(current_user.id))
        # делаем имя контейнера
        container_name = f"bot_{bot_id.replace('-', '')[:24]}"
        # получаем номер порта который пока не используется
        api_port = await self.bot_repo.allocate_port()
        # переводит фильтры в нужный формат
        long_filters, short_filters = resolve_filters(
            preset=body.strategy_preset,
            direction=body.direction,
            custom_long=[f.model_dump() for f in body.entry_filters_long] if body.entry_filters_long else None,
            custom_short=[f.model_dump() for f in body.entry_filters_short] if body.entry_filters_short else None,
        )
        # преобразуем стопы в нужный формат: проценты движения цены -> доли маржи
        take_profit = BotService._build_take_profit(body.take_profit_percent, body.leverage)
        stop_loss = BotService._build_stoploss(body.stop_loss_enabled, body.stop_loss_percent, body.leverage)

        # Ключ ищем строго среди ключей текущего пользователя: api_key_id приходит из
        # тела запроса, и выборка «по одному id» позволяла запустить бота на чужом
        # биржевом ключе. Проверка стоит до create(): нет смысла занимать порт и
        # писать строку бота, если запрос всё равно будет отбит.
        api_key = None
        if body.api_key_id is not None:
            api_key = await self.api_keys_repo.get_api_key_by_id(body.api_key_id, current_user.id)
            if api_key is None:
                logger.warning(
                    "Bot creation rejected: API key not found for this user",
                    extra={"user_id": current_user.id, "api_key_id": body.api_key_id},
                )
                # 404, а не 403: по коду ответа нельзя отличить чужой ключ от несуществующего
                raise NotFoundError("API-ключ не найден")
        else:
            logger.info(
                "Bot work with dry-run",
                extra={"user_id": current_user.id},
            )

        # проверка на то что нет бота на той же торговой паре
        # стоит до создания чтобы не создавать файлы просто так
        if api_key is not None and not body.dry_run:
            await self._ensure_pair_is_free(
                api_key_id=api_key.id,
                pair=body.pair,
                statuses=None,
                exclude_bot_id=None,
                user_id=current_user.id,
                message=(
                    "На этом API-ключе уже есть бот на паре {pair} — «{name}». "
                    "Биржа считает их сделки одной позицией: вход второго увеличит позицию первого, "
                    "а стоп первого закроет её целиком. Удалите существующего бота или выберите другую пару."
                ),
            )

        exchange_key = decrypt(api_key.api_key_encrypted) if api_key else ""
        exchange_secret = decrypt(api_key.api_secret_encrypted) if api_key else ""

        api_username = "freqtrader"
        # пароль для api
        api_password = secrets.token_urlsafe(16)
        # сохранение всего в бд
        bot = Bot(
            id=bot_id,
            user_id=current_user.id,
            name=body.name,
            pair=body.pair,
            leverage=body.leverage,
            direction=body.direction,
            strategy_preset=body.strategy_preset,
            entry_filters_long=long_filters,
            entry_filters_short=short_filters,
            take_profit=take_profit,
            stop_loss=stop_loss,
            # Трейлинг-стоп выключен намеренно и переключателя в интерфейсе больше нет.
            # В шаблоне стратегии его дистанция и порог захардкожены (0.001 / 0.002), а
            # freqtrade делит их на плечо: при x10 это 0.01% и 0.02% движения цены. Стоп
            # взводился бы сразу и обрезал каждый выигрыш до ~0.1% маржи вместо
            # пользовательского take-profit, оставляя убытки полноразмерными.
            # Включать имеет смысл только вместе с осмысленными числами (отсюда и пустая
            # trailing_config) и после разбора аварийных выходов: с "stoploss_on_exchange"
            # трейлинг заставляет перевыставлять стоп-ордер на бирже на каждом новом пике.
            trailing_stop=False,
            trailing_config=None,
            dry_run=body.dry_run,
            status="created",
            container_name=container_name,
            api_port=api_port,
            api_username=api_username,
            api_password=api_password,
            api_key_id=body.api_key_id,
            stake_amount=body.stake_amount,
            tradable_balance_ratio=body.tradable_balance_ratio,
        )

        await self.bot_repo.create(bot)
        logger.info(
            "Bot created",
            extra={
                "user_id": current_user.id,
                "bot_id": bot.id,
                "bot_name": bot.name,
            },
        )

        # создаем файлы в bots_data
        await BotFileManager.materialize_bot_files(
            bot,
            current_user.id,
            exchange_key,
            exchange_secret,
            # Порт ВНУТРИ контейнера, а не выданный боту api_port: докер пробрасывает
            # INTERNAL_API_PORT наружу на bot.api_port, и listen_port в config.json
            # должен совпадать с внутренней стороной этого маппинга.
            docker_manager.INTERNAL_API_PORT,
            jwt_secret=secrets.token_hex(32),
            ws_token=secrets.token_urlsafe(24),
        )
        logger.info(
            "Bot files created",
            extra={
                "user_id": current_user.id,
                "bot_id": bot.id,
            },
        )

        return bot

    async def start_bot(self, bot: Bot):
        """Запускает контейнер для уже созданного бота."""
        logger.info(
            "Bot starting",
            extra={
                "user_id": bot.user_id,
                "bot_id": bot.id,
                "bot_name": bot.name,
            },
        )
        # Тот же порог, что и при создании: /bots/{id}/start дёргается и по боту,
        # который воркер уже остановил из-за баланса. Проверка — до перевода статуса
        # в "starting", иначе отбитый бот залипнет в этом статусе.
        if not bot.dry_run:
            owner = await self.bot_repo.get_user(bot.user_id)
            if owner is not None and not is_balance_sufficient(owner):
                logger.warning(
                    "Bot start rejected: service balance below minimum",
                    extra={
                        "bot_id": bot.id,
                        "user_id": bot.user_id,
                        "service_balance": owner.service_balance,
                        "min_balance": settings.MIN_SERVICE_BALANCE_RUB,
                    },
                )
                raise PaymentRequiredError(cannot_start_message())

            # дополнительная проврка на наличие бота с той же парой, на том же ключе
            # вроде даже не нужна, но пусть будет)
            if bot.api_key_id is not None:
                await self._ensure_pair_is_free(
                    api_key_id=bot.api_key_id,
                    pair=bot.pair,
                    statuses=("starting", "running"),
                    exclude_bot_id=bot.id,
                    user_id=bot.user_id,
                    message=(
                        "Бот «{name}» уже торгует парой {pair} на этом API-ключе. "
                        "Биржа считает их сделки одной позицией — остановите его, прежде чем запускать этого."
                    ),
                )

        # получаем папку с настройками бота
        bot_dir = BotService._bot_dir(bot.id)
        if not (bot_dir / "config.json").exists():
            logger.error(
                "No bot files found",
                extra={
                    "user_id": bot.user_id,
                    "bot_id": bot.id,
                },
            )
            raise NotFoundError("Не найдены файлы бота")

        # меняем статус на starting
        await self.bot_repo.change_bot_status("starting", bot)

        try:
            # проверяем что образ freqtrade есть на сервере
            docker_manager.ensure_image()
            # запускаем контейнеро бота

            logger.info(
                "Running docker container",
                extra={
                    "bot_id": bot.id,
                    "container_name": bot.container_name,
                    "api_port": bot.api_port,
                },
            )
            container = docker_manager.run_bot_container(
                container_name=bot.container_name,
                bot_data_dir=bot_dir,
                api_port_external=bot.api_port,
            )
            logger.info(
                "Container successfully started",
                extra={
                    "user_id": bot.user_id,
                    "bot_id": bot.id,
                    "container_id": container.id,
                },
            )
            # меняем данные о статусе и контейнере в бд
            await self.bot_repo.change_container_id(container.id, bot)
            await self.bot_repo.change_bot_status("running", bot)
            # Гасим текст прошлого отказа (например, остановки из-за баланса) — иначе
            # у работающего бота на /home так и висит старое сообщение.
            await self.bot_repo.add_error_message(None, bot)
            logger.info(
                "Bot status changed",
                extra={
                    "bot_id": bot.id,
                    "old_status": bot.status,
                    "new_status": "starting",
                },
            )

        except Exception as e:
            # Теги ставятся на scope запроса (его создаёт FastApiIntegration), поэтому
            # никуда не протекут. Отдельный capture_exception не нужен: LoggingIntegration
            # отправит logger.exception ниже в Glitchtip сама.
            sentry_sdk.set_tag("bot_id", bot.id)
            sentry_sdk.set_tag("user_id", str(bot.user_id))
            logger.exception(
                "Couldn't start the container",
                extra={
                    "bot_id": bot.id,
                    "user_id": bot.user_id,
                },
            )
            await self.bot_repo.change_bot_status("error", bot)
            await self.bot_repo.add_error_message(str(e)[:500], bot)

        return bot

    async def stop_bot(self, bot: Bot) -> Bot:
        logger.info(
            "Stopping the bot",
            extra={
                "bot_id": bot.id,
                "user_id": bot.user_id,
            },
        )
        if bot.container_id:
            docker_manager.stop_container(bot.container_id)
            logger.info(
                "Container successfully stoped",
                extra={
                    "user_id": bot.user_id,
                    "bot_id": bot.id,
                    "container_id": bot.container_id,
                },
            )

            ans = await self.bot_repo.change_bot_status("stopped", bot)

            return ans
        logger.error(
            "Container id not found",
            extra={
                "user_id": bot.user_id,
                "bot_id": bot.id,
            },
        )
        raise BadRequestError("У бота не найден id контейнера")

    async def delete_bot(self, bot: Bot) -> None:
        """
        Мягкое удаление: контейнер и файлы бота убираем физически, а строку в БД только
        помечаем is_active=False. Физический DELETE унёс бы по CASCADE все сделки бота,
        и общая статистика пользователя (P&L, winrate, график) менялась бы задним числом.
        """
        logger.info(
            "Deleting the bot",
            extra={
                "bot_id": bot.id,
                "user_id": bot.user_id,
            },
        )
        if bot.container_id:
            logger.info(
                "Removing container",
                extra={
                    "bot_id": bot.id,
                    "container_id": bot.container_id,
                },
            )
            docker_manager.remove_container(bot.container_id)
        else:
            logger.warning(
                "Bot had no container_id",
                extra={
                    "user_id": bot.user_id,
                    "bot_id": bot.id,
                },
            )

        bot_dir = BotService._bot_dir(bot.id)
        if bot_dir.exists():
            try:
                shutil.rmtree(bot_dir)
            except Exception:
                sentry_sdk.set_tag("bot_id", bot.id)
                sentry_sdk.set_tag("user_id", str(bot.user_id))
                logger.exception(
                    "Couldn't delete bot dir",
                    extra={
                        "user_id": bot.user_id,
                        "bot_id": bot.id,
                    },
                )
        else:
            logger.warning(
                "Bot dir nor found",
                extra={
                    "user_id": bot.user_id,
                    "bot_id": bot.id,
                },
            )

        await self.bot_repo.archive_bot(bot)
        logger.info(
            "Bot deleted",
            extra={
                "bot_id": bot.id,
                "user_id": bot.user_id,
            },
        )

    async def get_user_bot(self, bot_id: str, user: User) -> Bot:
        """Достаёт бота с проверкой, что он принадлежит текущему пользователю."""
        bot = await self.bot_repo.get_bot_by_id(bot_id)
        if bot is None:
            raise NotFoundError("Бот не найден")
        if bot.user_id != user.id:
            raise NotFoundError("Бот не найден")
        # архивированный бот для пользователя не существует: его нельзя ни запустить,
        # ни удалить повторно, хотя строка в БД осталась ради истории сделок
        if not bot.is_active:
            raise NotFoundError("Бот не найден")
        return bot

    @staticmethod
    async def get_logs(bot: Bot, tail: int):
        if not bot.container_id:
            return {"logs": ""}
        logs = docker_manager.get_container_logs(bot.container_id, tail=tail)
        return {"logs": logs}

    @staticmethod
    async def freqtrade_status(bot: Bot):
        data = freqtrade_client.get_status(bot)
        if data is None:
            raise NotFoundError("Не удалось получить открытые сделки")
        return data
