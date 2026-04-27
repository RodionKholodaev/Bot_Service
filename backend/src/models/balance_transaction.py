from datetime import datetime, timezone
from sqlalchemy import Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column
from src.database import Base


class BalanceTransaction(Base):
    __tablename__ = "balance_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # положительный — пополнение, отрицательный — списание
    amount: Mapped[float] = mapped_column(Float, nullable=False)

    # deposit / commission / refund
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    
    # привязка к сделке если тип — commission
    trade_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("trades.id", ondelete="SET NULL"), nullable=True
    )
    

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )