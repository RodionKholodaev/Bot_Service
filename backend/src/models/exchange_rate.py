# src/models/exchange_rate.py
from typing import Optional
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.orm import Mapped, mapped_column
from src.database import Base

class ExchangeRate(Base):
    __tablename__ = "exchange_rates"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    rate: Mapped[float] = mapped_column(nullable=False)  # RUB за 1 USDT
    source: Mapped[str] = mapped_column(default="binance")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    @classmethod
    async def get_latest(cls, db) -> Optional['ExchangeRate']:
        """Получить последний сохранённый курс"""
        result = await db.execute(
            select(cls).order_by(cls.created_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()
    
    @classmethod
    async def save_rate(cls, db, rate: float, source: str = "api") -> 'ExchangeRate':
        """Сохранить курс в БД"""
        rate_record = cls(rate=rate, source=source)
        db.add(rate_record)
        await db.commit()
        await db.refresh(rate_record)
        return rate_record