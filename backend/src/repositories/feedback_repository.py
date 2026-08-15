from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from src.models.feedback import Feedback


class FeedbackRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id, topic, message, email, rating):
        feedback = Feedback(
            user_id=user_id,
            topic=topic,
            message=message,
            email=email,
            rating=rating,
        )
        self.db.add(feedback)
        await self.db.flush()
        await self.db.refresh(feedback)
        return feedback

    async def count_since(self, user_id: int, since: datetime) -> int:
        """Сколько отзывов пользователь оставил начиная с момента since — для антиспама."""
        result = await self.db.execute(
            select(func.count())
            .select_from(Feedback)
            .where(Feedback.user_id == user_id, Feedback.created_at >= since)
        )
        return result.scalar_one()

    async def list_all(self):
        result = await self.db.execute(
            select(Feedback).order_by(Feedback.created_at.desc())
        )
        return result.scalars().all()
