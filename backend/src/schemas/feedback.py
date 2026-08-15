from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class FeedbackCreate(BaseModel):
    """Тело POST /feedback. Ограничения совпадают с теми, что проверяет фронт."""

    topic: Literal["idea", "bug", "ux", "other"]
    message: str = Field(..., min_length=10, max_length=2000)
    email: EmailStr | None = None
    rating: int | None = Field(default=None, ge=1, le=5)


class FeedbackOut(BaseModel):
    """Ответ на успешную отправку — фронту хватает факта 201, отдаём минимум."""

    id: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )
