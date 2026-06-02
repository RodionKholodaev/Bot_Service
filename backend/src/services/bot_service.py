from src.repositories.bot_repository import BotRepository
from src.models.user import User
from src.schemas.bot import BotCreate
from src.services.strategy_presets import resolve_filters
import uuid
import secrets
from src.models.bot import Bot
from src.services.bot_file_manager import BotFileManager
from src.repositories.api_keys_repository import ApiKeysRepository
from src.core.crypto import decrypt
from src.config import settings
from pathlib import Path
from src.services import docker_manager, freqtrade_client
import logging
import shutil
from src.core.exceptions import NotFoundError, BadRequestError
logger = logging.getLogger(__name__)

class BotService:
    def __init__(self, db):
        self.db = db
        self.bot_repo = BotRepository(db)
        self.api_keys_repo = ApiKeysRepository(db)

    @staticmethod
    def _build_take_profit(percent: float) -> dict:
        """Превращает 4 (процентов) в minimal_roi {"0": 0.04}."""
        return {"0": round(percent / 100.0, 6)}

    @staticmethod
    def _build_stoploss(enabled: bool, percent: float | None) -> float:
        """
        Возвращает stoploss в формате freqtrade (отрицательное число от цены).
        Если SL выключен — кладём -0.99 (фактически отключено).
        """
        if not enabled or percent is None:
            return -0.99
        return -round(percent / 100.0, 6)
    
    @staticmethod
    def _bot_dir(bot_id: str) -> Path:
        return settings.BOTS_DATA_DIR / bot_id

    async def _get_user_bot (self, bot_id, user:User):
        bot = await self.bot_repo.get_bot_by_id(bot_id)
        if bot is None:
            raise NotFoundError("Бот не найден")
        if bot.user_id != user.id:
            raise NotFoundError("Бот не найден")
        return bot
    

    async def create_bot(self, current_user: User, body: BotCreate):

        """
        Создаем папку бота, делаем запись в бд
        """
        bot_id = str(uuid.uuid4())
        # делаем имя контейнера
        container_name = f"bot_{bot_id.replace('-', '')[:24]}"
        # получаем номер порта который пока не используется
        api_port = await self.bot_repo.allocate_port()
        # переводит фильтры в нужный формат
        long_filters, short_filters = resolve_filters(
            preset=body.strategy_preset,
            direction=body.direction,
            custom_long=[f.model_dump() for f in body.entry_filters_long]
            if body.entry_filters_long else None,
            custom_short=[f.model_dump() for f in body.entry_filters_short]
            if body.entry_filters_short else None,
        )
        # преобразуем стопы в нужный формат
        take_profit = BotService._build_take_profit(body.take_profit_percent)
        stop_loss = BotService._build_stoploss(body.stop_loss_enabled, body.stop_loss_percent)
        
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
            trailing_stop=False,
            trailing_config=None,
            dry_run=body.dry_run,
            status="created",
            container_name=container_name,
            api_port=api_port,
            api_username=api_username,
            api_password=api_password,
            api_key_id = body.api_key_id,
            stake_amount=body.stake_amount,                   
            tradable_balance_ratio=body.tradable_balance_ratio,
        )

        await self.bot_repo.create(bot)
        await self.db.commit()

        # получаем ключи из бд
        api_key = None
        if bot.api_key_id:
            api_key = await self.api_keys_repo.get_api_key_by_id(bot.api_key_id)
        
        exchange_key = decrypt(api_key.api_key_encrypted) if api_key else ""
        exchange_secret = decrypt(api_key.api_secret_encrypted) if api_key else ""

        # создаем файлы в bots_data
        await BotFileManager.materialize_bot_files(
            bot,
            current_user.id,
            exchange_key,
            exchange_secret,
            api_port,
            jwt_secret=secrets.token_hex(32),
            ws_token=secrets.token_urlsafe(24),
        )

        return bot
    
    async def start_bot(self, bot: Bot):
        """Запускает контейнер для уже созданного бота."""
        # получаем папку с настройками бота
        bot_dir = BotService._bot_dir(bot.id)
        if not (bot_dir / "config.json").exists():
            raise NotFoundError("Не найдены файлы бота")
        
        # меняем статус на starting
        await self.bot_repo.change_bot_status("starting", bot)
        await self.db.commit()

        try:
            # проверяем что образ freqtrade есть на сервере
            docker_manager.ensure_image()
            # запускаем контейнеро бота
            container = docker_manager.run_bot_container(
                container_name=bot.container_name,
                bot_data_dir=bot_dir,
                api_port_external=bot.api_port,
            )
            # меняем данные о статусе и контейнере в бд
            await self.bot_repo.change_container_id(container.id, bot)
            await self.bot_repo.change_bot_status("running", bot)
            await self.db.commit()

        except Exception as e:
            logger.exception("Не удалось запустить контейнер")
            await self.bot_repo.change_bot_status("error", bot)
            await self.bot_repo.add_error_message(str(e)[:500], bot)
            await self.db.commit()

        return bot
    
    async def stop_bot(self, bot: Bot) -> Bot:
        if bot.container_id:
            docker_manager.stop_container(bot.container_id)
            ans = await self.bot_repo.change_bot_status("stopped", bot)
            await self.db.commit()
            return ans
        raise BadRequestError("У бота не найден id")
        
        


    async def delete_bot(self, bot: Bot) -> None:
        if bot.container_id:
            docker_manager.remove_container(bot.container_id)

        bot_dir = BotService._bot_dir(bot.id)
        if bot_dir.exists():
            try:
                shutil.rmtree(bot_dir)
            except Exception:
                logger.exception(f"Не удалось удалить папку бота {bot_dir}")

        await self.bot_repo.delete_bot(bot)
        await self.db.commit()

    async def get_user_bot(self, bot_id: str, user: User) -> Bot:
        """Достаёт бота с проверкой, что он принадлежит текущему пользователю."""
        bot = await self.bot_repo.get_bot_by_id(bot_id)
        if bot is None:
            raise NotFoundError("Бот не найден")
        if bot.user_id != user.id:
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
    