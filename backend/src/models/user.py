from datetime import datetime, timezone
from sqlalchemy import Integer, String, DateTime, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column
from src.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # баланс для оплаты комиссии сервиса
    service_balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    
    # доля прибыли, которую берёт сервис (0.20 = 20%)
    commission_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.20)
    
    # False — аккаунт заблокирован
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )