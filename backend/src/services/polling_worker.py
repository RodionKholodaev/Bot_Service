# src/services/polling_worker.py
"""
Фоновый воркер: каждые 30 секунд проверяет, что боты живы и торгуют, синхронизирует
сделки из freqtrade в нашу таблицу trades и обновляет Bot.total_profit.

Здоровье бота определяется по его REST API, а не по статусу контейнера: freqtrade
умеет отказывать, не убивая контейнер (см. _check_and_sync_bot).

Запускается один раз при старте приложения через lifespan в main.py.
"""

import asyncio
import logging
from datetime import UTC, datetime

import httpx
import sentry_sdk
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import AsyncSessionLocal
from src.models.bot import Bot
from src.models.trade import Trade
from src.models.user import User
from src.repositories.bot_repository import BotRepository
from src.repositories.trade_repository import TradeRepository
from src.services import docker_manager
from src.services.commission_service import CommissionService

logger = logging.getLogger(__name__)

POLL_INTERVAL = 30  # секунды

# Таймаут на любой запрос к REST API бота.
BOT_API_TIMEOUT = 5.0

# Сколько опросов подряд бот должен молчать, прежде чем мы признаем его мёртвым.
# 3 × 30 с = 90 с. Одного промаха мало: столько же длится окно перезапуска контейнера
# по restart_policy, а freqtrade после старта ещё десятки секунд грузит рынки и
# пейрлист — при этом Bot.status становится "running" сразу после запуска контейнера.
MAX_PING_MISSES = 3

# Сколько строк логов упавшего контейнера забирать из docker.
CONTAINER_LOG_TAIL_LINES = 50

# Сколько символов этого хвоста класть в extra={...} лог-записи. Полный хвост уходит
# в контекст Glitchtip, а extra попадает ещё и в текст telegram-алерта — там нужен
# короткий кусок, который читается с телефона, а не вся простыня.
CONTAINER_LOG_TAIL_CHARS = 1000


# ──────────────────────────────────────────────────────────────
# Запрос к freqtrade REST API
# ──────────────────────────────────────────────────────────────


async def _bot_api_get(
    bot: Bot,
    client: httpx.AsyncClient,
    path: str,
    *,
    auth: bool = True,
    params: dict | None = None,
) -> httpx.Response:
    """
    GET к REST API конкретного бота. Каждый контейнер пробрасывает свой 8080 на bot.api_port.

    Исключение наружу не глушим: насколько провал важен, решает вызывающий — для /ping
    это ожидаемое событие, для остальных ручек уже нет.
    """
    resp = await client.get(
        f"http://{settings.BOT_API_HOST}:{bot.api_port}{path}",
        auth=(bot.api_username, bot.api_password) if auth else None,
        params=params,
        timeout=BOT_API_TIMEOUT,
    )
    resp.raise_for_status()
    return resp


def _describe(exc: Exception) -> str:
    """
    Текст ошибки для лога. С типом: у httpx-исключений сообщение часто пустое
    (ReadTimeout('')), и один str(exc) не даёт понять, что вообще произошло.
    """
    return f"{type(exc).__name__}: {exc}"


async def _ping_bot(bot: Bot, client: httpx.AsyncClient) -> str | None:
    """
    Отвечает ли REST API бота: None — ответил, строка — текст ошибки.

    Причину возвращаем, а не логируем на месте. Одиночный промах — норма (рестарт
    контейнера, медленный старт freqtrade), и писать про него в лог нечего, но после
    MAX_PING_MISSES она уходит в critical-алерт: иначе разработчик видит только
    "не отвечает 90 секунд" и не знает, отказ это соединения, таймаут или 502.

    /api/v1/ping у freqtrade публичный — авторизация не нужна, поэтому неверный пароль
    не будет выглядеть как смерть бота.
    """
    try:
        await _bot_api_get(bot, client, "/api/v1/ping", auth=False)
        return None
    except Exception as exc:
        return _describe(exc)


async def _fetch_bot_state(bot: Bot, client: httpx.AsyncClient) -> str | None:
    """
    Состояние торгового цикла freqtrade из /api/v1/show_config: "running" / "paused" / "stopped".
    None — если ответа нет или поля state в нём не оказалось.
    """
    try:
        resp = await _bot_api_get(bot, client, "/api/v1/show_config")
        return resp.json().get("state")
    except Exception as exc:
        # warning, а не debug: сюда попадают уже после успешного ping, то есть API бота
        # живо и провал — это 401/5xx/битый ответ, а не перезапуск контейнера. При этом
        # None неотличим от здорового бота: проверка на "stopped" просто не сработает,
        # и вставший freqtrade будет считаться работающим сколько угодно долго.
        logger.warning(
            "Failed to fetch bot state",
            extra={"bot_id": bot.id, "error": _describe(exc)},
        )
        return None


async def _fetch_trades(bot: Bot, client: httpx.AsyncClient) -> list[dict]:
    """
    Запрашивает /api/v1/trades у freqtrade-контейнера.
    Возвращает пустой список если контейнер недоступен.
    """
    try:
        resp = await _bot_api_get(bot, client, "/api/v1/trades", params={"limit": 500})
        trades = resp.json().get("trades", [])
        logger.debug(
            "Trades fetched from freqtrade",
            extra={"bot_id": bot.id, "trades_count": len(trades)},
        )
        return trades
    except Exception as exc:
        # warning по той же причине, что и в _fetch_bot_state: ping только что прошёл.
        # Пустой список неотличим от "сделок нет" — молча не синхронизируются сделки
        # и не начисляется комиссия.
        logger.warning(
            "Failed to fetch trades from freqtrade",
            extra={"bot_id": bot.id, "error": _describe(exc)},
        )
        return []


# ──────────────────────────────────────────────────────────────
# Обработка одного бота
# ──────────────────────────────────────────────────────────────


def _parse_dt(value: str | None) -> datetime | None:
    """Парсит ISO-строку от freqtrade в datetime с UTC."""
    if not value:
        return None
    # freqtrade отдаёт "2024-04-27T10:30:00.000000+00:00" или без TZ
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        logger.warning(
            "Failed to parse datetime",
            extra={"raw_value": value},
        )
        return None


def _required_dt(value: str | None, bot_id: str, field: str) -> datetime:
    """
    То же, что _parse_dt, но с подстановкой текущего времени вместо None.

    open_time в модели NOT NULL, а close_time — признак "сделка закрыта" для всей
    статистики. Оставить их пустыми нельзя: без open_time INSERT падает и синхронизация
    бота откатывается каждый цикл, а закрытая сделка без close_time навсегда выпадает из
    статистики (все запросы фильтруют close_time IS NOT NULL) и на каждом опросе заново
    выглядит "только что закрывшейся". Приблизительное время лучше потерянной сделки.
    """
    parsed = _parse_dt(value)
    if parsed is not None:
        return parsed

    logger.warning(
        "Trade has no usable timestamp, falling back to current time",
        extra={"bot_id": bot_id, "field": field, "raw_value": value},
    )
    return datetime.now(UTC)


async def _async_bot_trades(db: AsyncSession, bot: Bot, raw_trades: list[dict]) -> None:
    """
    Синхронизирует список сделок от freqtrade в нашу таблицу.
    Обновляет Bot.total_profit и начисляет комиссию при закрытии.
    """
    botrepository = BotRepository(db)
    traderepository = TradeRepository(db)

    user: User | None = await botrepository.get_user(bot.user_id)
    if not user:
        logger.warning(
            "User not found for bot, skipping trade sync",
            extra={"bot_id": bot.id, "user_id": bot.user_id},
        )
        return

    for ft in raw_trades:
        ft_id: int = ft["trade_id"]
        is_open: bool = ft.get("is_open", True)

        existing: Trade | None = await traderepository.get_trade(bot.id, ft_id)

        if existing is None:
            # Новая сделка — создаём запись
            logger.info(
                "New trade detected, creating record",
                extra={"bot_id": bot.id, "trade_id": ft_id, "pair": ft.get("pair")},
            )
            trade = Trade(
                bot_id=bot.id,
                user_id=bot.user_id,
                freqtrade_trade_id=ft_id,
                leverage=bot.leverage,
                pair=ft.get("pair", ""),
                direction="long" if not ft.get("is_short", False) else "short",
                open_rate=ft.get("open_rate", 0.0),
                close_rate=ft.get("close_rate") if not is_open else None,
                amount=ft.get("amount", 0.0),
                profit_usdt=ft.get("profit_abs") if not is_open else None,
                profit_pct=(ft.get("profit_ratio") or 0.0) * 100 if not is_open else None,
                exit_reason=ft.get("exit_reason") if not is_open else None,
                open_time=_required_dt(ft.get("open_date"), bot.id, "open_date"),
                close_time=(_required_dt(ft.get("close_date"), bot.id, "close_date") if not is_open else None),
            )
            db.add(trade)
            await db.flush()  # получаем trade.id для дальнейшей логики

        else:
            trade = existing
            # Данные закрытия дозаписываем, пока пуста цена закрытия, а НЕ пока пусто
            # close_time. close_time проставляется всегда: _required_dt при отсутствии
            # даты подставляет текущее время, поэтому уже после первого прохода сделка
            # по нему выглядит записанной. Если freqtrade в тот момент ещё не досчитал
            # результат (сделка не открыта, но close_rate/profit_abs пустые), второй
            # попытки не было бы никогда — так в боевой БД и осели 7 сделок из 1722 с
            # NULL в close_rate. По close_rate же мы возвращаемся к сделке каждый цикл,
            # пока freqtrade не отдаст цену.
            if not is_open and trade.close_rate is None:
                logger.info(
                    "Existing trade closed, updating record",
                    extra={
                        "bot_id": bot.id,
                        "trade_id": ft_id,
                        "close_rate": ft.get("close_rate"),
                        "profit_usdt": ft.get("profit_abs"),
                    },
                )
                trade.close_rate = ft.get("close_rate")
                trade.profit_usdt = ft.get("profit_abs")
                trade.profit_pct = (ft.get("profit_ratio") or 0.0) * 100
                trade.exit_reason = ft.get("exit_reason")
                trade.close_time = _required_dt(ft.get("close_date"), bot.id, "close_date")

        # Учёт закрытой сделки — прибавка к Bot.total_profit и комиссия — отдельно от
        # дозаписи выше и одной точкой на обе ветки. Три условия, и каждое обязательно:
        #
        # profit_usdt is not None — по недосчитанному результату начислять нельзя.
        #   process_commission взял бы profit=0, поставил commission_paid и закрыл сделку
        #   для учёта навсегда: комиссия по ней уже не возьмётся, в Bot.total_profit она
        #   не попадёт, даже когда freqtrade досчитает прибыль. Ровно это и случилось с
        #   теми семью сделками. Дожидаемся результата и учитываем сделку один раз.
        # not trade.commission_paid — дублирует защиту внутри сервиса намеренно: freqtrade
        #   отдаёт последние 500 сделок на каждый опрос, и без проверки здесь мы звали бы
        #   сервис на каждую из них каждые 30 секунд ради предупреждения в лог.
        if not is_open and trade.profit_usdt is not None and not trade.commission_paid:
            logger.info(
                "Closed trade is being accounted",
                extra={
                    "bot_id": bot.id,
                    "trade_id": ft_id,
                    "profit_usdt": trade.profit_usdt,
                },
            )
            await CommissionService.process_commission(trade, user, bot)

    await db.commit()
    logger.info(
        "Trade sync completed for bot",
        extra={"bot_id": bot.id, "processed_trades": len(raw_trades)},
    )


# ──────────────────────────────────────────────────────────────
# Реакция на отказ бота
# ──────────────────────────────────────────────────────────────


async def _mark_bot_failed(db: AsyncSession, bot: Bot, reason: str, detail: str | None = None) -> None:
    """
    Единая реакция на любой обнаруженный отказ: алерт разработчику, статус "error"
    в БД и остановка контейнера.

    reason — короткая формулировка, она уезжает в Bot.error_message и оттуда в интерфейс
    пользователю (String(500)). detail — сырой текст ошибки, только для разработчика:
    в БД его класть нельзя ни по длине, ни по смыслу.
    """
    container_status = docker_manager.get_container_status(bot.container_id) if bot.container_id else None
    # При отказе на старте freqtrade падает до того, как поднимет свой REST API,
    # поэтому /api/v1/logs недоступен и docker-логи — единственный источник причины.
    tail_logs = (
        docker_manager.get_container_logs(bot.container_id, tail=CONTAINER_LOG_TAIL_LINES) if bot.container_id else ""
    )

    # new_scope, а не глобальный sentry_sdk.set_tag: воркер — одна долгоживущая таска,
    # и теги/контекст, выставленные напрямую, залипли бы на всех последующих событиях
    # этой таски (логи контейнера одного бота уехали бы к другому).

    # открываем конверт, который sentry отправит одним алертом
    with sentry_sdk.new_scope() as scope:
        scope.set_tag("bot_id", bot.id)
        scope.set_tag("user_id", str(bot.user_id))
        scope.set_context("container_logs", {"tail": tail_logs})
        # critical, а не error: бот мёртв, торговля встала — это не самовосстанавливающийся
        # сбой, разработчик должен узнать сразу. Отдельный capture_message не нужен —
        # LoggingIntegration сама отправит эту запись в Glitchtip, иначе на один сбой
        # было бы два события.
        logger.critical(
            "Bot stopped working",
            extra={
                "bot_id": bot.id,
                "user_id": bot.user_id,
                "reason": reason,
                "detail": detail,
                "container_status": container_status,
                "container_logs_tail": tail_logs[-CONTAINER_LOG_TAIL_CHARS:],
            },
        )

    await BotRepository(db).change_bot_status("error", bot)
    await BotRepository(db).add_error_message(reason, bot)
    # Коммитим до остановки контейнера. Если остановка упадёт, статус "error" всё равно
    # должен остаться в БД — иначе бот навсегда останется "running", а воркер будет слать
    # алерт каждые POLL_INTERVAL секунд.
    await db.commit()

    # Контейнер останавливаем последним и именно как реакцию, а не как способ узнать об
    # отказе: он держит проброшенный порт (allocate_port считает его занятым) и до 512 МБ
    # памяти, а при отказе на старте процесс freqtrade зависает в shutdown и сам не умрёт.
    if bot.container_id:
        try:
            docker_manager.stop_container(bot.container_id)
        except Exception:
            logger.exception(
                "Failed to stop container of a failed bot",
                extra={"bot_id": bot.id, "container_id": bot.container_id},
            )


# ──────────────────────────────────────────────────────────────
# Проверка и синхронизация одного бота
# ──────────────────────────────────────────────────────────────


async def _check_and_sync_bot(
    db: AsyncSession,
    bot: Bot,
    client: httpx.AsyncClient,
    ping_misses: dict[str, int],
) -> None:
    """
    Один цикл работы с одним ботом: проверить, что он жив, синхронизировать сделки,
    проверить, что он ещё торгует. ping_misses мутируется на месте — это счётчик
    промахов подряд, общий для всех циклов воркера.
    """
    # 1. Жив ли процесс freqtrade. На статус контейнера полагаться нельзя: при отказе
    # на старте процесс зависает в shutdown (незакрытый non-daemon поток websocket'ов
    # ccxt), и docker до бесконечности показывает "running" у мёртвого бота.
    ping_error = await _ping_bot(bot, client)
    if ping_error is not None:
        misses = ping_misses.get(bot.id, 0) + 1
        ping_misses[bot.id] = misses
        logger.warning(
            "Bot API is not responding",
            extra={
                "bot_id": bot.id,
                "misses": misses,
                "max_misses": MAX_PING_MISSES,
                "error": ping_error,
            },
        )
        if misses >= MAX_PING_MISSES:
            await _mark_bot_failed(
                db,
                bot,
                f"Bot API is not responding for {misses * POLL_INTERVAL} seconds",
                detail=ping_error,
            )
            del ping_misses[bot.id]
        return

    ping_misses.pop(bot.id, None)

    # 2. Сделки синхронизируем до проверки состояния: если ниже окажется, что бот встал,
    # контейнер будет остановлен и добрать сделки станет неоткуда.
    raw = await _fetch_trades(bot, client)
    if raw:
        # сохронизировали сделки
        await _async_bot_trades(db, bot, raw)

    # 3. Живой процесс ещё не значит, что бот торгует: поймав OperationalException,
    # freqtrade переводит себя в "stopped" и продолжает крутиться пустым циклом —
    # контейнер, порт и ping при этом выглядят полностью здоровыми. "paused" —
    # штатное состояние, в нём freqtrade продолжает обработку.
    state = await _fetch_bot_state(bot, client)
    if state == "stopped":
        await _mark_bot_failed(db, bot, "Freqtrade stopped trading (state: stopped)")


# ──────────────────────────────────────────────────────────────
# Основной цикл
# ──────────────────────────────────────────────────────────────


async def run_polling_worker() -> None:
    """
    Синхронизирует сделки бота с бд сервиса.
    Бесконечный цикл. Запускать через asyncio.create_task() в lifespan.
    """
    logger.info(
        "Polling worker started",
        extra={"interval_seconds": POLL_INTERVAL},
    )

    # {bot_id: сколько опросов подряд бот не ответил на ping}. Держим в памяти, а не в БД:
    # миграций в проекте нет, а цена потери счётчика при рестарте бэкенда — повторное
    # обнаружение отказа через MAX_PING_MISSES циклов.
    ping_misses: dict[str, int] = {}

    # создаем клиента для общения по http
    async with httpx.AsyncClient() as client:
        while True:
            try:
                # получили сессию для работы с бд
                async with AsyncSessionLocal() as db:
                    try:
                        # получили активных ботов
                        running_bots = await BotRepository(db).get_all_active_bots()
                        logger.debug(
                            "Active bots fetched",
                            extra={"bots_count": len(running_bots)},
                        )

                        # чистим счётчики ботов, которых больше нет в работе (остановлены
                        # пользователем, удалены или уже переведены в error)
                        active_bot_ids = {bot.id for bot in running_bots}
                        for tracked_id in list(ping_misses):
                            if tracked_id not in active_bot_ids:
                                del ping_misses[tracked_id]

                        # пробегаемся по ботам
                        for bot in running_bots:
                            try:
                                await _check_and_sync_bot(db, bot, client, ping_misses)
                            except Exception:
                                with sentry_sdk.new_scope() as scope:
                                    scope.set_tag("bot_id", bot.id)
                                    scope.set_tag("user_id", str(bot.user_id))
                                    logger.exception(
                                        "Failed to sync trades for bot",
                                        extra={"bot_id": bot.id, "user_id": bot.user_id},
                                    )
                                await db.rollback()
                                continue

                    except Exception as exc:
                        logger.exception(
                            "Polling worker inner error",
                            extra={"error": str(exc)},
                        )
                        await db.rollback()
                    finally:
                        await db.close()

            except Exception as exc:
                # critical, а не exception/error: это внешний цикл воркера — если сюда
                # долетело исключение, синхронизация сделок встала для ВСЕХ ботов сразу,
                # и это нужно увидеть сразу, а не при следующей проверке логов.
                logger.critical(
                    "Polling worker outer error — trade sync stopped for this cycle",
                    extra={"error": str(exc)},
                    exc_info=True,
                )
            # ждем указаное время
            await asyncio.sleep(POLL_INTERVAL)
