# src/services/stats_service.py
"""
Агрегирует статистику из таблиц trades и bots.
Никуда не ходит по сети — только читает нашу БД.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.bot import Bot
from src.models.trade import Trade
from src.models.user import User
from src.schemas.stats import (
    TradeOut, PnlPoint, BotStats, PortfolioStats, HomeStats
)
from src.repositories.bot_repository import BotRepository
from src.repositories.trade_repository import TradeRepository

from datetime import timedelta

# ──────────────────────────────────────────────
# Вспомогательные функции
# ──────────────────────────────────────────────

def _build_pnl_chart(trades: list[Trade]) -> list[PnlPoint]:
    """
    Строит накопленный P&L по времени из списка закрытых сделок.
    Сделки уже отсортированы по close_time.
    """
    cumulative = 0.0
    points: list[PnlPoint] = []
    for t in trades:
        if t.close_time is None or t.profit_usdt is None:
            continue
        cumulative += t.profit_usdt
        points.append(PnlPoint(
            ts=t.close_time.strftime("%d.%m %H:%M"),
            value=round(cumulative, 4),
        ))
    return points


def _max_drawdown(trades: list[Trade]) -> Optional[float]:
    """
    Считает максимальную просадку как наибольшее падение
    кумулятивного P&L от пика до минимума (в USDT, возвращаем %).
    Возвращает отрицательное число или None если сделок нет.
    """
    if not trades:
        return None

    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0

    for t in trades:
        if t.profit_usdt is None:
            continue
        cumulative += t.profit_usdt
        if cumulative > peak:
            peak = cumulative
        dd = cumulative - peak
        if dd < max_dd:
            max_dd = dd

    # переводим в процент от пика
    if peak == 0:
        return None
    return round((max_dd / peak) * 100, 2) if max_dd < 0 else 0.0


def _trades_to_out(trades: list[Trade]) -> list[TradeOut]:
    return [TradeOut.model_validate(t) for t in trades]


# ──────────────────────────────────────────────
# Публичные функции
# ──────────────────────────────────────────────

async def get_bot_stats(
    db: AsyncSession,
    bot: Bot,
    period_days: Optional[int] = None,
    recent_limit: int = 20,
) -> BotStats:
    """Статистика по одному боту."""

    # Базовый запрос — только закрытые сделки этого бота
    query = await TradeRepository(db).get_bot_close_trades(bot.user_id, bot.id)

    if period_days:
        from datetime import timedelta

        since = datetime.now(timezone.utc) - timedelta(days=period_days)
        query = query.where(Trade.close_time >= since)

    query = query.order_by(Trade.close_time.asc())

    result = await db.execute(query)

    closed_trades: list[Trade] = list(result.scalars().all())

    wins = [t for t in closed_trades if (t.profit_usdt or 0) > 0]
    losses = [t for t in closed_trades if (t.profit_usdt or 0) <= 0]

    total = len(closed_trades)
    win_count = len(wins)
    loss_count = len(losses)

    avg_profit_pct: Optional[float] = None
    if closed_trades:
        pcts = [t.profit_pct for t in closed_trades if t.profit_pct is not None]
        avg_profit_pct = round(sum(pcts) / len(pcts), 2) if pcts else None

    recent = list(reversed(closed_trades[-recent_limit:]))

    return BotStats(
        bot_id=bot.id,
        name=bot.name,
        pair=bot.pair,
        leverage=bot.leverage,
        direction=bot.direction,
        strategy_preset=bot.strategy_preset,
        status=bot.status,
        total_profit=round(bot.total_profit, 4),
        trades_total=total,
        trades_win=win_count,
        trades_loss=loss_count,
        winrate=round((win_count / total * 100), 1) if total else 0.0,
        avg_profit_pct=avg_profit_pct,
        max_drawdown_pct=_max_drawdown(closed_trades),
        pnl_chart=_build_pnl_chart(closed_trades),
        recent_trades=_trades_to_out(recent),
    )


async def get_portfolio_stats(
    db: AsyncSession,
    user: User,
    period_days: Optional[int] = None,
    recent_limit: int = 30,
) -> PortfolioStats:
    """Агрегированная статистика по всем ботам пользователя."""
    #репозитории
    botrepository = BotRepository(db)
    traderepository = TradeRepository(db)

    bots = await botrepository.get_user_active_bots(user.id)

    # Все закрытые сделки пользователя за период
    query = await traderepository.get_all_close_trades(user.id)

    if period_days:
        from datetime import timedelta
        since = datetime.now(timezone.utc) - timedelta(days=period_days)
        query = query.filter(Trade.close_time >= since)

    result = await db.execute(query)
    all_trades = list(result.scalars().all())

    wins = sum(1 for t in all_trades if (t.profit_usdt or 0) > 0)
    total = len(all_trades)
    losses = total - wins

    recent = list(reversed(all_trades[-recent_limit:]))

    bots_running = sum(1 for b in bots if b.status == "running")
    bots_stopped = len(bots) - bots_running
    total_profit = sum(b.total_profit for b in bots)

    # Краткая сводка по каждому боту для сайдбара
    bots_stats = [await get_bot_stats(db, b, period_days) for b in bots]

    return PortfolioStats(
        total_profit=round(total_profit, 4),
        trades_total=total,
        trades_win=wins,
        trades_loss=losses,
        winrate=round((wins / total * 100), 1) if total else 0.0,
        max_drawdown_pct=_max_drawdown(all_trades),
        bots_running=bots_running,
        bots_stopped=bots_stopped,
        pnl_chart=_build_pnl_chart(all_trades),
        recent_trades=_trades_to_out(recent),
        bots=bots_stats,
    )




async def get_home_stats(db: AsyncSession, user: User) -> HomeStats:
    bots: list[Bot] = list(await BotRepository(db).get_user_active_bots(user.id))

    total_profit = sum(b.total_profit for b in bots)
    bots_running = sum(1 for b in bots if b.status == "running")

    # 👇 Прибыль за последние 7 дней
    since = datetime.now(timezone.utc) - timedelta(days=7)
    weekly_trades = await TradeRepository(db).get_weekly_trades(user.id, since)

    weekly_profit = round(sum(t.profit_usdt or 0 for t in weekly_trades), 4)

    # 👇 Сумма в управлении = stake_amount всех активных ботов
    funds_under_management = round(
        sum(b.stake_amount for b in bots if b.status in ("running", "starting")), 2
    )

    # recent_trades: list[Trade] = (
    #     db.query(Trade)
    #     .filter(Trade.user_id == user.id, Trade.close_time.isnot(None))
    #     .order_by(Trade.close_time.desc())
    #     .limit(10)
    #     .all()
    # )

    return HomeStats(
        service_balance=round(user.service_balance, 2),
        total_profit=round(total_profit, 4),
        bots_running=bots_running,
        bots_total=len(bots),
        weekly_profit=weekly_profit,        
        funds_under_management=funds_under_management,  
    )
