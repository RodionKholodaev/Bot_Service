from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


# ── Тип одного фильтра ────────────────────────────────────
class FilterRule(BaseModel):
    indicator: Literal["rsi", "cci"]
    timeframe: Literal["1m", "5m", "15m", "30m", "1h", "4h"]
    condition: Literal["less", "greater", "less_equal", "greater_equal"]
    value: float


# ── Что присылает фронт при создании бота ────────────────
class BotCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    pair: str = Field(..., min_length=3, max_length=50)
    # пример: "XRP/USDT:USDT" — формат фьючерсной пары bybit/binance в freqtrade

    leverage: int = Field(..., ge=1, le=125)
    direction: Literal["long", "short", "both"]

    strategy_preset: Literal["conservative", "moderate", "aggressive", "custom"]

    # Если preset != custom — эти поля можно не присылать (бэкенд раскроет из пресета).
    # Если preset == custom — нужно прислать оба массива (или хотя бы соответствующий direction).
    entry_filters_long: list[FilterRule] | None = None
    entry_filters_short: list[FilterRule] | None = None

    # Take profit — одно число в процентах от цены (например 4 = +4%)
    take_profit_percent: float = Field(..., gt=0, le=100)

    # Stop loss
    stop_loss_enabled: bool = True
    stop_loss_percent: float | None = Field(default=None, gt=0, le=100)
    # если stop_loss_enabled=False — поле игнорируется

    dry_run: bool = True


# ── Что отдаём фронту ─────────────────────────────────────
class BotPublic(BaseModel):
    id: str
    name: str
    pair: str
    leverage: int
    direction: str
    strategy_preset: str

    entry_filters_long: list[dict]
    entry_filters_short: list[dict]
    take_profit: dict
    stop_loss: float

    dry_run: bool
    status: str
    error_message: str | None

    api_port: int
    created_at: datetime

    model_config = {"from_attributes": True}
