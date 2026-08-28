from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.services.strategy_presets import get_preset


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

    # Фильтры и проценты можно не присылать: при preset != custom их подставит сам пресет
    # (см. apply_preset_defaults ниже и resolve_filters). Присланное всегда сильнее
    # пресета — интерфейс шлёт то, что видно на экране, а человек мог поправить руками.
    entry_filters_long: list[FilterRule] | None = None
    entry_filters_short: list[FilterRule] | None = None

    # Take profit — движение ЦЕНЫ в процентах (например 1.5 = цена прошла +1.5%).
    # Не доля маржи: плечо на эту величину не влияет, оно только умножает результат.
    take_profit_percent: float | None = Field(default=None, gt=0, le=100)

    # Stop loss — тоже движение цены в процентах
    stop_loss_enabled: bool | None = None
    stop_loss_percent: float | None = Field(default=None, gt=0, le=100)
    # если stop_loss_enabled=False — поле игнорируется

    dry_run: bool = True

    api_key_id: int | None
    # Депозит бота целиком. Границы обязательны: без них 0 или отрицательный депозит
    # доезжал до конфига freqtrade, и бот молча не открывал ни одной сделки.
    stake_amount: float = Field(..., gt=0)
    # Доля депозита на одну сделку: 0.2 = 20%. Больше 1 быть не может — сделка не может
    # быть больше депозита, из которого её открывают.
    tradable_balance_ratio: float = Field(..., gt=0, le=1)

    @model_validator(mode="after")
    def apply_preset_defaults(self):
        """Пресет заполняет TP/SL, которых нет в теле запроса.

        Стоит первым: остальные проверки (и граница «процент * плечо») должны считаться
        уже по итоговым значениям, иначе запрос с одним лишь именем пресета отбивался бы
        как неполный, а через интерфейс тот же пресет создавал бы бота молча.
        """
        preset = None if self.strategy_preset == "custom" else get_preset(self.strategy_preset)

        if self.take_profit_percent is None:
            if preset is None:
                raise ValueError("Для custom-стратегии нужен take_profit_percent")
            self.take_profit_percent = preset["take_profit_percent"]

        if self.stop_loss_enabled is None:
            self.stop_loss_enabled = preset["stop_loss_enabled"] if preset else True

        if self.stop_loss_enabled and self.stop_loss_percent is None and preset is not None:
            self.stop_loss_percent = preset["stop_loss_percent"]

        return self

    @model_validator(mode="after")
    def validate_filters_by_direction(self):
        """Фильтры обязательны только для custom — остальным их даст пресет."""
        if self.strategy_preset != "custom":
            return self

        if self.direction in ("long", "both") and not self.entry_filters_long:
            raise ValueError("Для направления long/both нужны entry_filters_long")

        if self.direction in ("short", "both") and not self.entry_filters_short:
            raise ValueError("Для направления short/both нужны entry_filters_short")
        return self

    @model_validator(mode="after")
    def validate_stop_loss(self):
        """Проверка stop loss параметров"""
        if self.stop_loss_enabled and self.stop_loss_percent is None:
            raise ValueError("Если stop_loss_enabled=true, нужен stop_loss_percent")

        # Проценты пользователя — движение цены; freqtrade меряет стоп в долях маржи, и
        # переводит их плечо (см. BotService._build_stoploss). Стоп в 100% маржи и дальше
        # даёт stoploss <= -1, а такой стоп бессмыслен: позиции уже нет, её ликвидировали.
        # Без этой проверки бот создавался бы, а контейнер падал при старте.
        if self.stop_loss_enabled and self.stop_loss_percent is not None:
            margin_share = self.stop_loss_percent * self.leverage
            if margin_share >= 100:
                max_percent = round(100 / self.leverage, 2)
                raise ValueError(
                    f"Стоп-лосс {self.stop_loss_percent}% при плече x{self.leverage} "
                    f"съедает всю маржу — позиция будет ликвидирована раньше. "
                    f"Максимум для этого плеча — {max_percent}% движения цены"
                )
        return self


# ── Готовые пресеты: их отдаём форме создания бота ────────
class StrategyPresetOut(BaseModel):
    """Пресет целиком — форма рисует карточку и заполняет по ней все поля стратегии.

    Иконка и цвет остаются на фронте: сериализовать React-компонент некуда.
    """

    key: str
    name: str
    description: str
    long_filters: list[FilterRule]
    short_filters: list[FilterRule]
    take_profit_percent: float
    stop_loss_percent: float | None
    stop_loss_enabled: bool


# ── Открытые сделки: спрашиваются перед удалением бота ────
class OpenTradeOut(BaseModel):
    """Открытая сделка бота. Нужна интерфейсу, чтобы предупредить при удалении:
    позиция останется на бирже, а связь с ней (sqlite бота) удаление уничтожит."""

    pair: str
    direction: str
    open_rate: float
    amount: float
    open_time: datetime

    model_config = {"from_attributes": True}


# ── Что отдаём фронту ─────────────────────────────────────
class BotPublic(BaseModel):
    id: str
    name: str
    pair: str
    leverage: int
    direction: str
    strategy_preset: str

    entry_filters_long: list[dict] = []
    entry_filters_short: list[dict] = []
    # Проценты в том виде, в каком их задал человек. Формат freqtrade (доли маржи,
    # умноженные на плечо) наружу не отдаём — по нему настройку не показать.
    take_profit_percent: float | None
    stop_loss_percent: float | None

    dry_run: bool
    status: str
    error_message: str | None

    api_port: int
    created_at: datetime
    total_profit: float = 0.0
    model_config = {"from_attributes": True}
