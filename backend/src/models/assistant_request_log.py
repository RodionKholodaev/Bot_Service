from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class AssistantRequestLog(Base):
    """Факт одного обращения пользователя к ИИ-ассистенту.

    Нужен только для rate limit (services/assistant/rate_limit.py): лимитер
    считает строки за последнюю минуту и за последние сутки. Переписка тут не
    хранится — её вообще никто не хранит, кроме вкладки браузера.
    """

    __tablename__ = "assistant_requests"

    # Таблица растёт на строку с каждого сообщения в чате, и каждый запрос
    # делает по ней два range-скана — поэтому индекс составной, ровно под
    # форму запроса (user_id = ? AND created_at >= ?). Отдельный индекс по
    # user_id не нужен: он покрывается префиксом составного.
    __table_args__ = (Index("ix_assistant_requests_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
