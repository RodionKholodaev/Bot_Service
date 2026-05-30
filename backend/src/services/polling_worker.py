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
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.commission_service import CommissionService
from src.database import AsyncSessionLocal
from src.models.bot import Bot
from src.models.trade import Trade
from src.models.user import User
from src.repositories.bot_repository import BotRepository
from src.repositories.trade_repository import TradeRepository
logger = logging.getLogger(__name__)

POLL_INTERVAL = 30  # секунды


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
        return data.get("trades", [])
    except Exception as exc:
        logger.debug("Bot %s freqtrade unavailable: %s", bot.id, exc)
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
        return None


async def _async_bot_trades(db: AsyncSession, bot: Bot, raw_trades: list[dict]) -> None:
    """
    Синхронизирует список сделок от freqtrade в нашу таблицу.
    Обновляет Bot.total_profit и начисляет комиссию при закрытии.
    """
    botrepository = BotRepository(db)
    traderepository = TradeRepository(db)
    
    user: User | None= await botrepository.get_user(bot.user_id)
    if not user:
        return

    for ft in raw_trades:
        ft_id: int = ft["trade_id"]
        is_open: bool = ft.get("is_open", True)

        existing: Trade | None = await traderepository.get_trade(bot.id, ft_id)

        if existing is None:
            # Новая сделка — создаём запись
            trade = Trade(
                bot_id=bot.id,
                user_id=bot.user_id,
                freqtrade_trade_id=ft_id,
                leverage = bot.leverage,
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
                await CommissionService.process_commission(trade,user,bot)

        else:
            # Сделка уже была — проверяем, не закрылась ли она
            if not is_open and existing.close_time is None:
                existing.close_rate = ft.get("close_rate")
                existing.profit_usdt = ft.get("profit_abs")
                existing.profit_pct = (ft.get("profit_ratio", 0.0) or 0.0) * 100
                existing.exit_reason = ft.get("exit_reason")
                existing.close_time = _parse_dt(ft.get("close_date"))
                await CommissionService.process_commission(existing,user,bot)

    await db.commit()


# ──────────────────────────────────────────────────────────────
# Основной цикл
# ──────────────────────────────────────────────────────────────

async def run_polling_worker() -> None:
    """
    Бесконечный цикл. Запускать через asyncio.create_task() в lifespan.
    """
    logger.info("Polling worker started (interval=%ds)", POLL_INTERVAL)

    async with httpx.AsyncClient() as client:
        while True:
            try:

                async with AsyncSessionLocal() as db:
                    try:
                    
                        running_bots = await BotRepository(db).get_all_active_bots()

                        for bot in running_bots:
                            raw = await _fetch_trades(bot, client)
                            if raw:
                                await _async_bot_trades(db, bot, raw)

                    except Exception as exc:
                        logger.exception("Polling worker error: %s", exc)
                        await db.rollback()
                    finally:
                        await db.close()

            except Exception as exc:
                logger.exception("Polling worker outer error: %s", exc)

            await asyncio.sleep(POLL_INTERVAL)