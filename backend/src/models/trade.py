from datetime import datetime, timezone
from sqlalchemy import Integer, String, DateTime, ForeignKey, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from src.database import Base


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    bot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ID сделки внутри freqtrade — защита от дублирования при повторном polling
    freqtrade_trade_id: Mapped[int] = mapped_column(Integer, nullable=False)

    pair: Mapped[str] = mapped_column(String(50), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    # long / short

    open_rate: Mapped[float] = mapped_column(Float, nullable=False)
    close_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    # nullable — сделка может быть ещё открыта

    amount: Mapped[float] = mapped_column(Float, nullable=False)
    # размер позиции в базовой валюте

    profit_usdt: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    commission_usdt: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # сколько сервис взял с этой сделки

    commission_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # True — уже списано с service_balance пользователя

    exit_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # tp / sl / trailing_sl / manual / force_sell

    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    close_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)