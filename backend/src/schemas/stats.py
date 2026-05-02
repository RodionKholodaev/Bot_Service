from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class TradeOut(BaseModel):
    id: int
    bot_id: str
    pair: str
    direction: str          # long / short
    open_rate: float
    close_rate: Optional[float]
    profit_usdt: Optional[float]
    profit_pct: Optional[float]
    exit_reason: Optional[str]
    open_time: datetime
    close_time: Optional[datetime]

    model_config = {"from_attributes": True}


class PnlPoint(BaseModel):
    """Одна точка для графика P&L по времени."""
    ts: str          # метка времени (ISO или DD.MM HH:MM)
    value: float     # накопленный profit_usdt к этому моменту


class BotStats(BaseModel):
    """Статистика по одному боту."""
    bot_id: str
    name: str
    pair: str
    leverage: int
    direction: str
    strategy_preset: str
    status: str
    total_profit: float      # из Bot.total_profit (USDT)
    trades_total: int
    trades_win: int
    trades_loss: int
    winrate: float           # 0..100
    avg_profit_pct: Optional[float]
    max_drawdown_pct: Optional[float]
    pnl_chart: list[PnlPoint]
    recent_trades: list[TradeOut]


class PortfolioStats(BaseModel):
    """Агрегат по всем ботам пользователя."""
    total_profit: float
    trades_total: int
    trades_win: int
    trades_loss: int
    winrate: float
    max_drawdown_pct: Optional[float]
    bots_running: int
    bots_stopped: int
    pnl_chart: list[PnlPoint]
    recent_trades: list[TradeOut]
    bots: list[BotStats]     # краткая сводка по каждому боту (для sidebar)


class HomeStats(BaseModel):
    """Минимальная статистика для главной страницы."""
    service_balance: float
    total_profit: float
    bots_running: int
    bots_total: int
    weekly_profit: float        
    funds_under_management: float  
