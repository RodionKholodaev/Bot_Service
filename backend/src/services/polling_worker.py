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
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.models.bot import Bot
from src.models.trade import Trade
from src.models.user import User

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


def _sync_bot_trades(db: Session, bot: Bot, raw_trades: list[dict]) -> None:
    """
    Синхронизирует список сделок от freqtrade в нашу таблицу.
    Обновляет Bot.total_profit и начисляет комиссию при закрытии.
    """
    user: User = db.query(User).filter(User.id == bot.user_id).first()
    if not user:
        return

    for ft in raw_trades:
        ft_id: int = ft["trade_id"]
        is_open: bool = ft.get("is_open", True)

        existing: Trade | None = (
            db.query(Trade)
            .filter(Trade.bot_id == bot.id, Trade.freqtrade_trade_id == ft_id)
            .first()
        )

        if existing is None:
            # Новая сделка — создаём запись
            trade = Trade(
                bot_id=bot.id,
                user_id=bot.user_id,
                freqtrade_trade_id=ft_id,
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
            db.flush()  # получаем trade.id для дальнейшей логики

            if not is_open:
                _handle_close(db, bot, user, trade)

        else:
            # Сделка уже была — проверяем, не закрылась ли она
            if not is_open and existing.close_time is None:
                existing.close_rate = ft.get("close_rate")
                existing.profit_usdt = ft.get("profit_abs")
                existing.profit_pct = (ft.get("profit_ratio", 0.0) or 0.0) * 100
                existing.exit_reason = ft.get("exit_reason")
                existing.close_time = _parse_dt(ft.get("close_date"))
                _handle_close(db, bot, user, existing)

    db.commit()


def _handle_close(db: Session, bot: Bot, user: User, trade: Trade) -> None:
    """
    Вызывается один раз при закрытии сделки:
    - обновляет Bot.total_profit
    - рассчитывает и списывает комиссию сервиса
    """
    profit = trade.profit_usdt or 0.0

    # Обновляем накопленный профит бота
    bot.total_profit = round(bot.total_profit + profit, 8)

    # Комиссия — только с прибыльных сделок
    if profit > 0 and not trade.commission_paid:
        commission = round(profit * user.commission_rate, 8)
        trade.commission_usdt = commission
        trade.commission_paid = True

        # Списываем с сервисного баланса пользователя
        user.service_balance = round(user.service_balance - commission, 8)

        # Суммарно списанная комиссия по боту
        bot.total_commission_paid = round(bot.total_commission_paid + commission, 8)

        logger.info(
            "Bot %s trade #%s closed: profit=%.4f USDT, commission=%.4f USDT",
            bot.id, trade.freqtrade_trade_id, profit, commission,
        )


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
                db: Session = SessionLocal()
                try:
                    running_bots: list[Bot] = (
                        db.query(Bot)
                        .filter(Bot.status == "running", Bot.is_active == True)
                        .all()
                    )

                    for bot in running_bots:
                        raw = await _fetch_trades(bot, client)
                        if raw:
                            _sync_bot_trades(db, bot, raw)

                except Exception as exc:
                    logger.exception("Polling worker error: %s", exc)
                    db.rollback()
                finally:
                    db.close()

            except Exception as exc:
                logger.exception("Polling worker outer error: %s", exc)

            await asyncio.sleep(POLL_INTERVAL)