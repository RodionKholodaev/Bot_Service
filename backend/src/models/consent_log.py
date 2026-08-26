from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class ConsentLog(Base):
    """Факт принятия одним пользователем одного юридического документа.

    Нужен для аудита при проверке РКН: по строке видно, кто, когда и какую
    именно редакцию документа принял. Пишется только согласие — отказа в
    таблице нет, отсутствие строки и есть отказ. Строки не обновляются и не
    удаляются: новая редакция документа даёт новую строку, а история остаётся.
    """

    __tablename__ = "consent_log"

    # Единственный осмысленный запрос по таблице — «какие согласия есть у этого
    # пользователя», индекс ровно под него. Отдельный индекс по user_id не
    # нужен: он покрывается префиксом составного.
    __table_args__ = (Index("ix_consent_log_user_document", "user_id", "document_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Одна из констант DOC_* из src/core/legal.py
    document_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # Редакция документа — та же дата, что напечатана на его странице
    document_version: Mapped[str] = mapped_column(String(32), nullable=False)

    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # IP на момент согласия — необязательное, но полезное доказательство.
    # None, если адрес определить не удалось (см. services/get_ip.py).
    # 45 символов — максимальная длина IPv6 в текстовом виде.
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
