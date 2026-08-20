"""
Агрегирует статистику из таблиц trades и bots.
Никуда не ходит по сети — только читает нашу БД.

Общее правило: все числа за период считаются по одному и тому же набору сделок.
Раньше прибыль бралась из Bot.total_profit (за всё время), а winrate и график —
из отфильтрованных по периоду сделок, и карточка "Общий P&L за период" на фронте
показывала не то же самое, что график под ней.
"""

import logging
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from src.models.bot import Bot
from src.models.trade import Trade
from src.models.user import User
from src.repositories.bot_repository import BotRepository
from src.repositories.trade_repository import TradeRepository
from src.schemas.stats import BotStats, BotSummary, HomeStats, PnlPoint, PortfolioStats, TradeOut

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Сервис
# ──────────────────────────────────────────────


class StatsService:
    # ── Вспомогательные методы ──────────────────

    @staticmethod
    def _period_start(period_days: int | None) -> datetime | None:
        """Начало периода в UTC. None — период "all", отсекать нечего."""
        if not period_days:
            return None
        return datetime.now(UTC) - timedelta(days=period_days)

    @staticmethod
    def _profit(trades: Sequence[Trade]) -> float:
        """Суммарный P&L по списку сделок."""
        return round(sum(t.profit_usdt or 0.0 for t in trades), 4)

    @staticmethod
    def _winrate(wins: int, total: int) -> float:
        return round(wins / total * 100, 1) if total else 0.0

    @staticmethod
    def _wins(trades: Sequence[Trade]) -> int:
        """
        Победы — строго profit > 0. Сделка, закрытая ровно в ноль, идёт в убыточные:
        отдельной "нейтральной" категории в статистике нет.
        """
        return sum(1 for t in trades if (t.profit_usdt or 0) > 0)

    @staticmethod
    def _build_pnl_chart(trades: Sequence[Trade]) -> list[PnlPoint]:
        """
        Строит накопленный P&L по времени из списка закрытых сделок.
        Сделки должны быть отсортированы по close_time — этим занимается репозиторий.
        """
        cumulative = 0.0
        points: list[PnlPoint] = []
        for t in trades:
            if t.close_time is None or t.profit_usdt is None:
                continue
            cumulative += t.profit_usdt
            points.append(
                PnlPoint(
                    ts=t.close_time,
                    value=round(cumulative, 4),
                )
            )
        logger.debug(
            "P&L chart built",
            extra={"points_count": len(points), "final_cumulative": round(cumulative, 4)},
        )
        return points

    @staticmethod
    def _max_drawdown(trades: Sequence[Trade], base_capital: float | None) -> float | None:
        """
        Максимальная просадка кривой капитала в процентах.

        База — вложенный капитал (stake_amount бота, для портфеля — сумма по ботам),
        а не пик накопленной прибыли, как было раньше. От пика прибыли число получалось
        бессмысленным: пик +0.5 USDT и падение на 0.4 давали -80%, а у бота, который ни
        разу не выходил в плюс, пик равнялся нулю и функция возвращала None — то есть
        "просадки не было" ровно там, где она максимальная.

        Возвращает отрицательное число, 0.0 если просадки не было, или None если считать
        не от чего: нет сделок либо неизвестен вложенный капитал.
        """
        if not trades or not base_capital or base_capital <= 0:
            return None

        equity = base_capital
        peak = base_capital
        max_dd_pct = 0.0

        for t in trades:
            if t.profit_usdt is None:
                continue
            equity += t.profit_usdt
            if equity > peak:
                peak = equity
            # peak >= base_capital > 0, деления на ноль тут быть не может
            dd_pct = (equity - peak) / peak * 100
            if dd_pct < max_dd_pct:
                max_dd_pct = dd_pct

        result = round(max_dd_pct, 2)
        logger.debug(
            "Max drawdown calculated",
            extra={
                "max_drawdown_pct": result,
                "trades_count": len(trades),
                "base_capital": base_capital,
            },
        )
        return result

    @staticmethod
    def _trades_to_out(trades: Sequence[Trade]) -> list[TradeOut]:
        return [TradeOut.model_validate(t) for t in trades]

    # ── Сборка ответов из уже загруженных сделок ─
    #
    # Чистые функции без похода в БД: портфель считает сводку по каждому боту из
    # одной общей выборки сделок, а не отдельным запросом на бота.

    @staticmethod
    def _build_bot_stats(
        bot: Bot,
        trades: Sequence[Trade],
        recent_limit: int,
    ) -> BotStats:
        total = len(trades)
        win_count = StatsService._wins(trades)

        pcts = [t.profit_pct for t in trades if t.profit_pct is not None]
        avg_profit_pct = round(sum(pcts) / len(pcts), 2) if pcts else None

        # сделки отсортированы по возрастанию close_time, последние — в конце
        recent = list(reversed(trades[-recent_limit:]))

        return BotStats(
            bot_id=bot.id,
            name=bot.name,
            pair=bot.pair,
            leverage=bot.leverage,
            direction=bot.direction,
            strategy_preset=bot.strategy_preset,
            status=bot.status,
            profit=StatsService._profit(trades),
            trades_total=total,
            trades_win=win_count,
            trades_loss=total - win_count,
            winrate=StatsService._winrate(win_count, total),
            avg_profit_pct=avg_profit_pct,
            max_drawdown_pct=StatsService._max_drawdown(trades, bot.stake_amount),
            pnl_chart=StatsService._build_pnl_chart(trades),
            recent_trades=StatsService._trades_to_out(recent),
        )

    @staticmethod
    def _build_bot_summary(bot: Bot, trades: Sequence[Trade]) -> BotSummary:
        total = len(trades)
        win_count = StatsService._wins(trades)
        return BotSummary(
            bot_id=bot.id,
            name=bot.name,
            pair=bot.pair,
            leverage=bot.leverage,
            direction=bot.direction,
            strategy_preset=bot.strategy_preset,
            status=bot.status,
            profit=StatsService._profit(trades),
            trades_total=total,
            winrate=StatsService._winrate(win_count, total),
        )

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
        period_days: int | None = None,
        recent_limit: int = 20,
    ) -> BotStats:
        """Статистика по одному боту."""

        logger.info(
            "Fetching bot stats",
            extra={"bot_id": bot.id, "period_days": period_days},
        )

        closed_trades = await self.trade_repo.get_closed_trades(
            bot.user_id,
            bot_id=bot.id,
            since=self._period_start(period_days),
        )

        stats = self._build_bot_stats(bot, closed_trades, recent_limit)

        logger.info(
            "Bot stats calculated",
            extra={
                "bot_id": bot.id,
                "trades_total": stats.trades_total,
                "winrate": stats.winrate,
            },
        )
        return stats

    async def get_portfolio_stats(
        self,
        user: User,
        period_days: int | None = None,
        recent_limit: int = 30,
    ) -> PortfolioStats:
        """Агрегированная статистика по всем ботам пользователя."""

        logger.info(
            "Fetching portfolio stats",
            extra={"user_id": user.id, "period_days": period_days},
        )

        bots = list(await self.bot_repo.get_user_active_bots(user.id))

        # Все закрытые сделки пользователя за период — в том числе сделки архивированных
        # ботов: удалённый бот пропадает из сайдбара, но заработанное им остаётся частью
        # истории портфеля и не должно исчезать из графика задним числом.
        all_trades = await self.trade_repo.get_closed_trades(
            user.id,
            since=self._period_start(period_days),
        )

        # раскладываем один раз по ботам, чтобы сводка для сайдбара не стоила
        # отдельного запроса на каждого бота
        trades_by_bot: dict[str, list[Trade]] = defaultdict(list)
        for t in all_trades:
            trades_by_bot[t.bot_id].append(t)

        total = len(all_trades)
        wins = self._wins(all_trades)

        recent = list(reversed(all_trades[-recent_limit:]))

        bots_running = sum(1 for b in bots if b.status == "running")
        # база для просадки — капитал, отданный ботам в работу
        invested = sum(b.stake_amount or 0.0 for b in bots)

        logger.info(
            "Portfolio stats calculated",
            extra={
                "user_id": user.id,
                "trades_total": total,
                "bots_running": bots_running,
            },
        )

        return PortfolioStats(
            profit=self._profit(all_trades),
            trades_total=total,
            trades_win=wins,
            trades_loss=total - wins,
            winrate=self._winrate(wins, total),
            max_drawdown_pct=self._max_drawdown(all_trades, invested),
            bots_running=bots_running,
            bots_stopped=len(bots) - bots_running,
            pnl_chart=self._build_pnl_chart(all_trades),
            recent_trades=self._trades_to_out(recent),
            bots=[self._build_bot_summary(b, trades_by_bot.get(b.id, [])) for b in bots],
        )

    async def get_home_stats(self, user: User) -> HomeStats:
        logger.info(
            "Fetching home stats",
            extra={"user_id": user.id},
        )

        # берём всех ботов одним запросом: общий профит считается за всё время и по
        # архивированным ботам тоже, а счётчики и сумма в управлении — только по активным
        all_bots: list[Bot] = list(await self.bot_repo.get_user_bots(user.id))
        active_bots = [b for b in all_bots if b.is_active]

        total_profit = sum(b.total_profit for b in all_bots)
        bots_running = sum(1 for b in active_bots if b.status == "running")

        # Прибыль за последние 7 дней
        since = datetime.now(UTC) - timedelta(days=7)
        weekly_trades = await self.trade_repo.get_closed_trades(user.id, since=since)
        weekly_profit = self._profit(weekly_trades)

        # Сумма в управлении = stake_amount всех работающих ботов
        funds_under_management = round(
            sum(b.stake_amount or 0.0 for b in active_bots if b.status in ("running", "starting")), 2
        )

        logger.info(
            "Home stats calculated",
            extra={
                "user_id": user.id,
                "bots_total": len(active_bots),
                "bots_running": bots_running,
                "weekly_profit": weekly_profit,
            },
        )

        return HomeStats(
            service_balance=round(user.service_balance, 2),
            total_profit=round(total_profit, 4),
            bots_running=bots_running,
            bots_total=len(active_bots),
            weekly_profit=weekly_profit,
            funds_under_management=funds_under_management,
        )
