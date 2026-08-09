# src/services/polling_worker.py
"""
Фоновый воркер: каждые 30 секунд синхронизирует сделки из freqtrade
в нашу таблицу trades и обновляет Bot.total_profit.

Запускается один раз при старте приложения через lifespan в main.py.
"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx
import sentry_sdk
from sqlalchemy.ext.asyncio import AsyncSession
from src.services import docker_manager
from src.services.commission_service import CommissionService
from src.database import AsyncSessionLocal
from src.models.bot import Bot
from src.models.trade import Trade
from src.models.user import User
from src.repositories.bot_repository import BotRepository
from src.repositories.trade_repository import TradeRepository

logger = logging.getLogger(__name__)

POLL_INTERVAL = 30  # секунды

# Сколько строк логов упавшего контейнера забирать из docker.
CONTAINER_LOG_TAIL_LINES = 50

# Сколько символов этого хвоста класть в extra={...} лог-записи. Полный хвост уходит
# в контекст Glitchtip, а extra попадает ещё и в текст telegram-алерта — там нужен
# короткий кусок, который читается с телефона, а не вся простыня.
CONTAINER_LOG_TAIL_CHARS = 1000


# ──────────────────────────────────────────────────────────────
# Запрос к freqtrade REST API
# ──────────────────────────────────────────────────────────────

async def _fetch_trades(bot: Bot, client: httpx.AsyncClient) -> list[dict]:
    """
    Запрашивает /api/v1/trades у freqtrade-контейнера.
    Возвращает пустой список если контейнер недоступен.
    """
    url = f"http://127.0.0.1:{bot.api_port}/api/v1/trades"
    try:
        resp = await client.get(
            url,
            auth=(bot.api_username, bot.api_password),
            params={"limit": 500},
            timeout=5.0,
        )
        resp.raise_for_status()
        data = resp.json()
        trades = data.get("trades", [])
        logger.debug(
            "Trades fetched from freqtrade",
            extra={"bot_id": bot.id, "trades_count": len(trades)},
        )
        return trades
    except Exception as exc:
        logger.debug(
            "Freqtrade container unavailable",
            extra={"bot_id": bot.id, "error": str(exc)},
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
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        logger.warning(
            "Failed to parse datetime",
            extra={"raw_value": value},
        )
        return None


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
                profit_pct=ft.get("profit_ratio", 0.0) * 100 if not is_open else None,
                exit_reason=ft.get("exit_reason") if not is_open else None,
                open_time=_parse_dt(ft.get("open_date")),
                close_time=_parse_dt(ft.get("close_date")) if not is_open else None,
            )
            db.add(trade)
            await db.flush()  # получаем trade.id для дальнейшей логики

            if not is_open:
                logger.info(
                    "New trade already closed, processing commission",
                    extra={
                        "bot_id": bot.id,
                        "trade_id": ft_id,
                        "profit_usdt": trade.profit_usdt,
                    },
                )
                await CommissionService.process_commission(trade, user, bot)

        else:
            # Сделка уже была — проверяем, не закрылась ли она
            if not is_open and existing.close_time is None:
                logger.info(
                    "Existing trade closed, updating record",
                    extra={
                        "bot_id": bot.id,
                        "trade_id": ft_id,
                        "profit_usdt": ft.get("profit_abs"),
                    },
                )
                existing.close_rate = ft.get("close_rate")
                existing.profit_usdt = ft.get("profit_abs")
                existing.profit_pct = (ft.get("profit_ratio", 0.0) or 0.0) * 100
                existing.exit_reason = ft.get("exit_reason")
                existing.close_time = _parse_dt(ft.get("close_date"))
                await CommissionService.process_commission(existing, user, bot)

    await db.commit()
    logger.info(
        "Trade sync completed for bot",
        extra={"bot_id": bot.id, "processed_trades": len(raw_trades)},
    )


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
                        # пробегаемся по ботам
                        for bot in running_bots:
                            try:
                                # получили статус бота
                                container_status = (
                                    docker_manager.get_container_status(bot.container_id)
                                    if bot.container_id
                                    else None
                                )
                                # если бот не работает, записываем логи
                                if container_status != "running" and bot.status == "running":
                                    tail_logs = (
                                        docker_manager.get_container_logs(
                                            bot.container_id, tail=CONTAINER_LOG_TAIL_LINES
                                        )
                                        if bot.container_id
                                        else ""
                                    )

                                    # new_scope, а не глобальный sentry_sdk.set_tag: воркер —
                                    # одна долгоживущая таска, и теги/контекст, выставленные
                                    # напрямую, залипли бы на всех последующих событиях этой
                                    # таски (логи контейнера одного бота уехали бы к другому).
                                    
                                    # откриваем конверт для которые sentry отправит одним алертом
                                    with sentry_sdk.new_scope() as scope:
                                        
                                        scope.set_tag("bot_id", bot.id)
                                        scope.set_tag("user_id", str(bot.user_id))
                                        scope.set_context("container_logs", {"tail": tail_logs})
                                        # critical, а не error: бот мёртв, торговля встала —
                                        # это не самовосстанавливающийся сбой, разработчик
                                        # должен узнать сразу. Отдельный capture_message не
                                        # нужен — LoggingIntegration сама отправит эту запись
                                        # в Glitchtip, иначе на один сбой было бы два события.
                                        logger.critical(
                                            "Bot container stopped unexpectedly",
                                            extra={
                                                "bot_id": bot.id,
                                                "user_id": bot.user_id,
                                                "container_status": container_status,
                                                "container_logs_tail": tail_logs[-CONTAINER_LOG_TAIL_CHARS:],
                                            },
                                        )
                                    # меняем статус бота
                                    await BotRepository(db).change_bot_status("error", bot)
                                    #  добавляем сообщение об ошибке
                                    await BotRepository(db).add_error_message(
                                        f"Container stopped unexpectedly (status: {container_status})", bot
                                    )
                                    # Коммитим здесь же. REST API freqtrade живёт внутри
                                    # контейнера, поэтому у неработающего контейнера на запрос
                                    # отвечать некому: _fetch_trades вернёт [] независимо от
                                    # того, сколько бот успел наторговать, _async_bot_trades
                                    # ниже не вызовется, и без этого коммита статус "error"
                                    # откатился бы при закрытии сессии — бот навсегда остался
                                    # бы "running" в БД, а воркер слал бы алерт каждые 30 секунд.
                                    await db.commit()
                                # достаем сделки (и если бот работает, и если не работает)
                                raw = await _fetch_trades(bot, client)
                                if raw:
                                    # сохронизировали сделки
                                    await _async_bot_trades(db, bot, raw)
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