from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class Bot(Base):
    __tablename__ = "bots"

    # UUID-строка. Используется и как PK, и как имя папки/контейнера.
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ── Что задаёт пользователь ───────────────────────────
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    pair: Mapped[str] = mapped_column(String(50), nullable=False)
    leverage: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # long / short

    # Имена достались от первой (неверной) трактовки и не совпадают со смыслом:
    # stake_amount — весь депозит бота, tradable_balance_ratio — доля депозита на одну
    # сделку (0.2 = 20%). В конфиг freqtrade они уезжают как available_capital/
    # dry_run_wallet и stake_amount = депозит * доля, см. freqtrade_config.generate_config.
    tradable_balance_ratio: Mapped[float]
    stake_amount: Mapped[float]

    strategy_preset: Mapped[str] = mapped_column(String(20), nullable=False)
    # custom / conservative / moderate / aggressive

    # JSON-списки фильтров
    entry_filters_long: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    entry_filters_short: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # take_profit хранится в формате minimal_roi freqtrade: {"0": 0.04}
    take_profit: Mapped[dict] = mapped_column(JSON, nullable=False)
    # если SL отключен — кладём -0.99 (фактически выключено)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)

    # Те же две настройки в том виде, в каком их задал человек: движение ЦЕНЫ в процентах.
    # Из take_profit/stop_loss их не восстановить, не поделив обратно на плечо — а показать
    # человеку его собственную настройку надо. Nullable: у ботов, созданных до этих полей,
    # значений нет. stop_loss_percent = None означает ещё и «стоп выключен».
    take_profit_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss_percent: Mapped[float | None] = mapped_column(Float, nullable=True)

    trailing_stop: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    trailing_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    api_key_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("exchange_api_keys.id", ondelete="SET NULL"), nullable=True
    )
    # False — бот архивирован (soft delete)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # накопленная прибыль в USDT, обновляется при каждом закрытии сделки
    total_profit: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # суммарно списанная комиссия сервиса
    total_commission_paid_usdt: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_commission_paid_rub: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # ── Что задаёт бэкенд ─────────────────────────────────
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="created")
    # created / starting / running / stopped / error

    container_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    container_name: Mapped[str] = mapped_column(String(100), nullable=False)
    api_port: Mapped[int] = mapped_column(Integer, nullable=False)
    api_username: Mapped[str] = mapped_column(String(50), nullable=False)
    api_password: Mapped[str] = mapped_column(String(100), nullable=False)

    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
