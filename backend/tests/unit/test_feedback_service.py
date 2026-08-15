"""
Юнит-тесты FeedbackService — в первую очередь антиспам-лимита.

Вся логика лимита опирается на один запрос в репозиторий: "сколько отзывов
пользователь оставил за последний час". Поэтому тестировать её можно без БД и
без HTTP — сервису подсовывается fake-репозиторий с заранее заданным счётчиком
(см. FakeFeedbackRepo ниже).
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.core.exceptions import TooManyRequestsError
from src.models.feedback import Feedback
from src.models.user import User
from src.schemas.feedback import FeedbackCreate
from src.services.feedback_service import FEEDBACK_LIMIT_PER_HOUR, FeedbackService


class FakeFeedbackRepo:
    """Fake вместо FeedbackRepository — вместо БД отдаёт заданный счётчик."""

    def __init__(self, recent_count: int):
        self._recent_count = recent_count
        self.created: list[Feedback] = []
        self.count_since_calls: list[tuple[int, datetime]] = []

    async def count_since(self, user_id, since):
        self.count_since_calls.append((user_id, since))
        return self._recent_count

    async def create(self, user_id, topic, message, email, rating):
        feedback = Feedback(
            id=len(self.created) + 1,
            user_id=user_id,
            topic=topic,
            message=message,
            email=email,
            rating=rating,
            created_at=datetime.now(timezone.utc),
        )
        self.created.append(feedback)
        return feedback


def make_payload(**overrides) -> FeedbackCreate:
    """Валидное тело запроса с разумными дефолтами."""
    data = {
        "topic": "idea",
        "message": "Хочу больше пресетов стратегий",
        "email": None,
        "rating": None,
    }
    data.update(overrides)
    return FeedbackCreate(**data)


@pytest.mark.asyncio
async def test_feedback_saved_when_under_limit():
    # Arrange
    user = User(id=1, email="test@test.com")
    repo = FakeFeedbackRepo(recent_count=FEEDBACK_LIMIT_PER_HOUR - 1)

    # Act
    result = await FeedbackService(repo).create_feedback(user, make_payload())

    # Assert
    assert len(repo.created) == 1
    assert result.user_id == 1
    assert result.topic == "idea"


@pytest.mark.asyncio
async def test_feedback_rejected_when_limit_reached():
    # Arrange
    user = User(id=1, email="test@test.com")
    repo = FakeFeedbackRepo(recent_count=FEEDBACK_LIMIT_PER_HOUR)

    # Act / Assert
    with pytest.raises(TooManyRequestsError):
        await FeedbackService(repo).create_feedback(user, make_payload())

    # отзыв не сохранён
    assert repo.created == []


@pytest.mark.asyncio
async def test_limit_counted_per_user_and_for_last_hour():
    # Arrange
    user = User(id=42, email="test@test.com")
    repo = FakeFeedbackRepo(recent_count=0)

    # Act
    await FeedbackService(repo).create_feedback(user, make_payload())

    # Assert
    # лимит считается по конкретному user_id и по окну ровно в час
    assert len(repo.count_since_calls) == 1
    user_id, since = repo.count_since_calls[0]
    assert user_id == 42

    expected_since = datetime.now(timezone.utc) - timedelta(hours=1)
    assert abs((since - expected_since).total_seconds()) < 5


@pytest.mark.asyncio
async def test_optional_fields_passed_to_repository():
    # Arrange
    user = User(id=7, email="test@test.com")
    repo = FakeFeedbackRepo(recent_count=0)

    payload = make_payload(topic="bug", email="answer@test.com", rating=4)

    # Act
    await FeedbackService(repo).create_feedback(user, payload)

    # Assert
    saved = repo.created[0]
    assert saved.topic == "bug"
    assert saved.email == "answer@test.com"
    assert saved.rating == 4
