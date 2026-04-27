from datetime import datetime, timezone
from sqlalchemy import Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from src.database import Base


class ExchangeApiKey(Base):
    __tablename__ = "exchange_api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    # binance / bybit / etc.

    label: Mapped[str] = mapped_column(String(100), nullable=False)
    # пользовательское название, например "Мой Binance"

    # Шифруются через Fernet перед записью, расшифровываются при чтении
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    api_secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )