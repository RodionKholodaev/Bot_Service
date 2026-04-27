from datetime import datetime, timezone
from sqlalchemy import Integer, String, DateTime, ForeignKey, Float, Boolean, JSON
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
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    # long / short / both

    strategy_preset: Mapped[str] = mapped_column(String(20), nullable=False)
    # custom / conservative / moderate / aggressive

    # JSON-списки фильтров. Для custom — присланные пользователем,
    # для пресетов — раскрытые на бэкенде по словарю пресетов.
    entry_filters_long: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    entry_filters_short: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # take_profit хранится в формате minimal_roi freqtrade: {"0": 0.04}
    take_profit: Mapped[dict] = mapped_column(JSON, nullable=False)
    # если SL отключен — кладём -0.99 (фактически выключено)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)

    trailing_stop: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    trailing_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

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
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
