"""
Агрегирует статистику из таблиц trades и bots.
Никуда не ходит по сети — только читает нашу БД.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.models.bot import Bot
from src.models.trade import Trade
from src.models.user import User
from src.schemas.stats import (
    TradeOut, PnlPoint, BotStats, PortfolioStats, HomeStats
)
from src.repositories.bot_repository import BotRepository
from src.repositories.trade_repository import TradeRepository

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Сервис
# ──────────────────────────────────────────────

class StatsService:

    # ── Вспомогательные методы ──────────────────

    @staticmethod
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
        logger.debug(
            "P&L chart built",
            extra={"points_count": len(points), "final_cumulative": round(cumulative, 4)},
        )
        return points

    @staticmethod
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
        result = round((max_dd / peak) * 100, 2) if max_dd < 0 else 0.0
        logger.debug(
            "Max drawdown calculated",
            extra={"max_drawdown_pct": result, "trades_count": len(trades)},
        )
        return result

    @staticmethod
    def _trades_to_out(trades: list[Trade]) -> list[TradeOut]:
        return [TradeOut.model_validate(t) for t in trades]

    # ── Инициализация ───────────────────────────

    def __init__(
        self,
        bot_repo: BotRepository,
        trade_repo: TradeRepository,
    ) -> None:
        self.bot_repo = bot_repo
        self.trade_repo = trade_repo
        logger.debug("StatsService initialized")

    async def get_bot_stats(
        self,
        bot: Bot,
        period_days: Optional[int] = None,
        recent_limit: int = 20,
    ) -> BotStats:
        """Статистика по одному боту."""

        logger.info(
            "Fetching bot stats",
            extra={"bot_id": bot.id, "period_days": period_days},
        )

        # Базовый запрос — только закрытые сделки этого бота
        query = await self.trade_repo.get_bot_close_trades(bot.user_id, bot.id)

        if period_days:
            since = datetime.now(timezone.utc) - timedelta(days=period_days)
            query = query.where(Trade.close_time >= since)

        query = query.order_by(Trade.close_time.asc())

        result = await self.trade_repo.db.execute(query)

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

        logger.info(
            "Bot stats calculated",
            extra={
                "bot_id": bot.id,
                "trades_total": total,
                "winrate": round((win_count / total * 100), 1) if total else 0.0,
            },
        )

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
            max_drawdown_pct=self._max_drawdown(closed_trades),
            pnl_chart=self._build_pnl_chart(closed_trades),
            recent_trades=self._trades_to_out(recent),
        )

    async def get_portfolio_stats(
        self,
        user: User,
        period_days: Optional[int] = None,
        recent_limit: int = 30,
    ) -> PortfolioStats:
        """Агрегированная статистика по всем ботам пользователя."""

        logger.info(
            "Fetching portfolio stats",
            extra={"user_id": user.id, "period_days": period_days},
        )

        bots = await self.bot_repo.get_user_active_bots(user.id)

        # Все закрытые сделки пользователя за период
        query = await self.trade_repo.get_all_close_trades(user.id)

        if period_days:
            since = datetime.now(timezone.utc) - timedelta(days=period_days)
            query = query.filter(Trade.close_time >= since)

        result = await self.trade_repo.db.execute(query)
        all_trades = list(result.scalars().all())

        wins = sum(1 for t in all_trades if (t.profit_usdt or 0) > 0)
        total = len(all_trades)
        losses = total - wins

        recent = list(reversed(all_trades[-recent_limit:]))

        bots_running = sum(1 for b in bots if b.status == "running")
        bots_stopped = len(bots) - bots_running
        total_profit = sum(b.total_profit for b in bots)

        # Краткая сводка по каждому боту для сайдбара
        bots_stats = [await self.get_bot_stats(b, period_days) for b in bots]

        logger.info(
            "Portfolio stats calculated",
            extra={
                "user_id": user.id,
                "trades_total": total,
                "bots_running": bots_running,
            },
        )

        return PortfolioStats(
            total_profit=round(total_profit, 4),
            trades_total=total,
            trades_win=wins,
            trades_loss=losses,
            winrate=round((wins / total * 100), 1) if total else 0.0,
            max_drawdown_pct=self._max_drawdown(all_trades),
            bots_running=bots_running,
            bots_stopped=bots_stopped,
            pnl_chart=self._build_pnl_chart(all_trades),
            recent_trades=self._trades_to_out(recent),
            bots=bots_stats,
        )

    async def get_home_stats(self, user: User) -> HomeStats:
        logger.info(
            "Fetching home stats",
            extra={"user_id": user.id},
        )

        bots: list[Bot] = list(await self.bot_repo.get_user_active_bots(user.id))

        total_profit = sum(b.total_profit for b in bots)
        bots_running = sum(1 for b in bots if b.status == "running")

        # Прибыль за последние 7 дней
        since = datetime.now(timezone.utc) - timedelta(days=7)
        weekly_trades = await self.trade_repo.get_weekly_trades(user.id, since)

        weekly_profit = round(sum(t.profit_usdt or 0 for t in weekly_trades), 4)

        # Сумма в управлении = stake_amount всех активных ботов
        funds_under_management = round(
            sum(b.stake_amount for b in bots if b.status in ("running", "starting")), 2
        )

        logger.info(
            "Home stats calculated",
            extra={
                "user_id": user.id,
                "bots_total": len(bots),
                "bots_running": bots_running,
                "weekly_profit": weekly_profit,
            },
        )

        return HomeStats(
            service_balance=round(user.service_balance, 2),
            total_profit=round(total_profit, 4),
            bots_running=bots_running,
            bots_total=len(bots),
            weekly_profit=weekly_profit,
            funds_under_management=funds_under_management,
        )