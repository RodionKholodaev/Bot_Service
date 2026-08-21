"""
Юнит-тесты AssistantRateLimiter — лимита обращений к платной модели.

Вся логика лимита сводится к двум запросам в репозиторий («сколько запросов
пользователь сделал за последнюю минуту» и «за последние сутки») и записи факта
запроса. Ни БД, ни сеть для этого не нужны: лимитеру подсовывается
FakeAssistantRequestRepo с заранее заданными счётчиками.

Отдельно проверяется, что при отказе запрос НЕ записывается — иначе отбитый
лимитом пользователь сам себе продлевал бы блокировку.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.core.exceptions import TooManyRequestsError
from src.models.user import User
from src.services.assistant.rate_limit import (
    ASSISTANT_LIMIT_PER_DAY,
    ASSISTANT_LIMIT_PER_MINUTE,
    AssistantRateLimiter,
)


class FakeAssistantRequestRepo:
    """Fake вместо AssistantRequestRepository — вместо БД отдаёт заданные счётчики.

    count_since вызывается дважды с разными окнами, поэтому фейк различает их по
    глубине since: минутное окно уходит в прошлое меньше чем на час, суточное — больше.
    """

    def __init__(self, *, minute_count: int = 0, day_count: int = 0):
        self._minute_count = minute_count
        self._day_count = day_count
        self.count_since_calls: list[tuple[int, datetime]] = []
        self.created: list[int] = []

    async def count_since(self, user_id, since):
        self.count_since_calls.append((user_id, since))
        age = datetime.now(UTC) - since
        return self._minute_count if age < timedelta(hours=1) else self._day_count

    async def create(self, user_id):
        self.created.append(user_id)


def make_user(*, user_id: int = 1) -> User:
    """Пользователь с минимумом полей — лимитеру нужен только id."""
    return User(id=user_id, email="test@test.com")


@pytest.mark.asyncio
async def test_request_registered_when_under_both_limits():
    # Arrange
    repo = FakeAssistantRequestRepo(
        minute_count=ASSISTANT_LIMIT_PER_MINUTE - 1,
        day_count=ASSISTANT_LIMIT_PER_DAY - 1,
    )

    # Act
    await AssistantRateLimiter(repo).check_and_register(make_user(user_id=7))

    # Assert
    # запрос отмечен до обращения к модели, иначе параллельные запросы
    # одного пользователя проскочили бы мимо счётчика
    assert repo.created == [7]


@pytest.mark.asyncio
async def test_request_rejected_when_minute_limit_reached():
    # Arrange
    # суточное окно ещё свободно — блокировать должно именно минутное
    repo = FakeAssistantRequestRepo(minute_count=ASSISTANT_LIMIT_PER_MINUTE, day_count=0)

    # Act / Assert
    with pytest.raises(TooManyRequestsError) as exc_info:
        await AssistantRateLimiter(repo).check_and_register(make_user())

    assert str(ASSISTANT_LIMIT_PER_MINUTE) in exc_info.value.detail
    # отбитый запрос не записан: иначе пользователь продлевал бы себе блокировку
    assert repo.created == []


@pytest.mark.asyncio
async def test_request_rejected_when_day_limit_reached():
    # Arrange
    # минутное окно чистое — значит сработает только суточное
    repo = FakeAssistantRequestRepo(minute_count=0, day_count=ASSISTANT_LIMIT_PER_DAY)

    # Act / Assert
    with pytest.raises(TooManyRequestsError) as exc_info:
        await AssistantRateLimiter(repo).check_and_register(make_user())

    assert str(ASSISTANT_LIMIT_PER_DAY) in exc_info.value.detail
    assert repo.created == []


@pytest.mark.asyncio
async def test_minute_and_day_messages_differ():
    # Arrange
    minute_repo = FakeAssistantRequestRepo(minute_count=ASSISTANT_LIMIT_PER_MINUTE, day_count=0)
    day_repo = FakeAssistantRequestRepo(minute_count=0, day_count=ASSISTANT_LIMIT_PER_DAY)

    # Act
    with pytest.raises(TooManyRequestsError) as minute_exc:
        await AssistantRateLimiter(minute_repo).check_and_register(make_user())
    with pytest.raises(TooManyRequestsError) as day_exc:
        await AssistantRateLimiter(day_repo).check_and_register(make_user())

    # Assert
    # тексты разные — пользователь должен понимать, подождать ему минуту или день
    assert minute_exc.value.detail != day_exc.value.detail


@pytest.mark.asyncio
async def test_windows_are_one_minute_and_one_day():
    # Arrange
    repo = FakeAssistantRequestRepo()

    # Act
    await AssistantRateLimiter(repo).check_and_register(make_user(user_id=42))

    # Assert
    assert len(repo.count_since_calls) == 2
    (_, minute_since), (_, day_since) = repo.count_since_calls

    now = datetime.now(UTC)
    # окна скользящие: отсчитываются от «сейчас», а не от начала минуты/суток
    assert abs((now - minute_since) - timedelta(minutes=1)).total_seconds() < 5
    assert abs((now - day_since) - timedelta(days=1)).total_seconds() < 5


@pytest.mark.asyncio
async def test_limits_counted_per_user():
    # Arrange
    repo = FakeAssistantRequestRepo()

    # Act
    await AssistantRateLimiter(repo).check_and_register(make_user(user_id=42))

    # Assert
    # оба окна считаются по одному и тому же пользователю
    assert [user_id for user_id, _ in repo.count_since_calls] == [42, 42]
