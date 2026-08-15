from datetime import datetime, timezone
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from src.database import Base


class Feedback(Base):
    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # idea / bug / ux / other
    topic: Mapped[str] = mapped_column(String(20), nullable=False)

    message: Mapped[str] = mapped_column(Text, nullable=False)

    # почта для ответа — необязательная, у пользователя уже есть email в профиле
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # оценка сервиса 1..5, необязательная
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
