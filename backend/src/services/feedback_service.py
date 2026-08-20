"""
Приём отзывов со страницы обратной связи.

Логика простая: проверить антиспам-лимит и сохранить отзыв.
В сеть не ходит — только наша БД через FeedbackRepository.
"""

import logging
from datetime import UTC, datetime, timedelta

from src.core.exceptions import TooManyRequestsError
from src.repositories.feedback_repository import FeedbackRepository
from src.services.feedback_notifier import notify_new_feedback

logger = logging.getLogger(__name__)

# Антиспам: сколько отзывов один пользователь может отправить за час.
FEEDBACK_LIMIT_PER_HOUR = 5


class FeedbackService:
    def __init__(self, repo):
        self.repo: FeedbackRepository = repo

    async def create_feedback(self, current_user, payload):
        """Сохраняет отзыв пользователя, отбивая слишком частые отправки."""

        # антиспам — считаем отзывы за последний час прямо в БД,
        # без Redis и внешних библиотек
        since = datetime.now(UTC) - timedelta(hours=1)
        recent_count = await self.repo.count_since(current_user.id, since)

        if recent_count >= FEEDBACK_LIMIT_PER_HOUR:
            logger.info(
                "Feedback rate limit exceeded",
                extra={"user_id": current_user.id, "recent_count": recent_count},
            )
            raise TooManyRequestsError(
                f"Слишком много отзывов: не больше {FEEDBACK_LIMIT_PER_HOUR} в час. Попробуйте отправить позже."
            )

        feedback = await self.repo.create(
            user_id=current_user.id,
            topic=payload.topic,
            message=payload.message,
            email=payload.email,
            rating=payload.rating,
        )

        logger.info(
            "Feedback submitted",
            extra={
                "user_id": current_user.id,
                "topic": payload.topic,
                "feedback_id": feedback.id,
                "rating": payload.rating,
            },
        )

        # уведомление разработчику — best effort, свои ошибки гасит само
        await notify_new_feedback(feedback, current_user)

        return feedback
