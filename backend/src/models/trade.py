from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
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
    leverage: Mapped[float] = mapped_column(Float, nullable=False)
    # плечо у сделки

    profit_usdt: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    exchange_rate_rub_usdt: Mapped[float] = mapped_column(Float, nullable=True)
    # курс рубля к usdt в момент закрытия сделки

    commission_usdt: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    commission_rub: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # сколько сервис взял с этой сделки

    commission_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # True — сделка уже учтена: профит добавлен в Bot.total_profit, а комиссия (если
    # сделка прибыльная) списана с service_balance. Ставится и на убыточных сделках —
    # это защита от повторного учёта, а не только признак списания.

    exit_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # tp / sl / trailing_sl / manual / force_sell

    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    close_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
