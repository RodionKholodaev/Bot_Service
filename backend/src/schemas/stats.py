from datetime import datetime

from pydantic import BaseModel


class TradeOut(BaseModel):
    id: int
    bot_id: str
    pair: str
    direction: str  # long / short
    open_rate: float
    close_rate: float | None
    profit_usdt: float | None
    profit_pct: float | None
    exit_reason: str | None
    open_time: datetime
    close_time: datetime | None

    model_config = {"from_attributes": True}


class PnlPoint(BaseModel):
    """Одна точка для графика P&L по времени."""

    ts: datetime  # время закрытия сделки в UTC, формат выбирает фронт
    value: float  # накопленный profit_usdt к этому моменту


class BotSummary(BaseModel):
    """
    Строка бота в сайдбаре статистики: только то, что реально рисует список.

    Отдельная схема, а не BotStats: сайдбару не нужны ни график, ни последние сделки,
    а при десятке ботов они раздували ответ портфеля в разы.
    """

    bot_id: str
    name: str
    pair: str
    leverage: int
    direction: str
    strategy_preset: str
    status: str
    dry_run: bool  # симуляция или боевой бот — фронт этим фильтрует список
    profit: float  # за выбранный период, USDT
    trades_total: int
    winrate: float  # 0..100


class BotStats(BaseModel):
    """Статистика по одному боту за выбранный период."""

    bot_id: str
    name: str
    pair: str
    leverage: int
    direction: str
    strategy_preset: str
    status: str
    profit: float  # сумма profit_usdt закрытых сделок за период
    trades_total: int
    trades_win: int
    trades_loss: int
    winrate: float  # 0..100
    avg_profit_pct: float | None
    max_drawdown_pct: float | None
    pnl_chart: list[PnlPoint]
    recent_trades: list[TradeOut]


class PortfolioStats(BaseModel):
    """Агрегат по всем ботам пользователя за выбранный период."""

    profit: float  # считается по тем же сделкам, что график и winrate
    trades_total: int
    trades_win: int
    trades_loss: int
    winrate: float
    max_drawdown_pct: float | None
    bots_running: int
    bots_stopped: int  # активные боты не в статусе running
    pnl_chart: list[PnlPoint]
    recent_trades: list[TradeOut]
    bots: list[BotSummary]


class HomeStats(BaseModel):
    """Минимальная статистика для главной страницы."""

    service_balance: float
    total_profit: float  # за всё время, по всем ботам включая архивные
    bots_running: int
    bots_total: int
    weekly_profit: float
    funds_under_management: float
