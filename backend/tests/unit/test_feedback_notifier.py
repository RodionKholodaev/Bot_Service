"""
Юнит-тесты уведомления о новом отзыве в Telegram.

В сеть, разумеется, не ходим: httpx.AsyncClient подменяется фейком, который
запоминает, что и куда «отправили». Главное, что здесь проверяется, — канал
молчит, пока не настроен, и что сбой Telegram не превращается в ошибку для
пользователя (отзыв к этому моменту уже сохранён в БД).
"""

from datetime import UTC, datetime

import httpx
import pytest

from src.config import settings
from src.models.feedback import Feedback
from src.models.user import User
from src.services import feedback_notifier
from src.services.feedback_notifier import notify_new_feedback


class FakeResponse:
    def raise_for_status(self):
        return None


class FakeAsyncClient:
    """Fake вместо httpx.AsyncClient — вместо запроса складывает его в sent."""

    sent: list[tuple[str, dict]] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, url, json):
        FakeAsyncClient.sent.append((url, json))
        return FakeResponse()


class BrokenAsyncClient(FakeAsyncClient):
    """Fake, изображающий недоступный Telegram."""

    async def post(self, url, json):
        raise httpx.ConnectError("telegram is down")


def make_feedback(**overrides) -> Feedback:
    """Сохранённый отзыв с разумными дефолтами."""
    data = {
        "id": 1,
        "user_id": 3,
        "topic": "idea",
        "message": "Хочу больше пресетов стратегий",
        "email": None,
        "rating": None,
        "created_at": datetime.now(UTC),
    }
    data.update(overrides)
    return Feedback(**data)


@pytest.fixture
def fake_client(monkeypatch):
    """Подменяет httpx.AsyncClient фейком и отдаёт список отправленных запросов."""
    FakeAsyncClient.sent = []
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    return FakeAsyncClient.sent


@pytest.fixture
def telegram_configured(monkeypatch):
    """Включает канал уведомлений (в conftest он погашен на все тесты)."""
    monkeypatch.setattr(settings, "TELEGRAM_FEEDBACK_BOT_TOKEN", "test-token")
    monkeypatch.setattr(settings, "TELEGRAM_FEEDBACK_CHAT_ID", "-100500")


@pytest.mark.asyncio
async def test_nothing_sent_when_not_configured(fake_client, monkeypatch):
    # Arrange
    # токен и chat_id не заданы — так выглядит дев-окружение по умолчанию
    monkeypatch.setattr(settings, "TELEGRAM_FEEDBACK_BOT_TOKEN", None)
    monkeypatch.setattr(settings, "TELEGRAM_FEEDBACK_CHAT_ID", None)

    user = User(id=3, email="user@test.com")

    # Act
    await notify_new_feedback(make_feedback(), user)

    # Assert
    assert fake_client == []


@pytest.mark.asyncio
async def test_nothing_sent_when_only_token_configured(fake_client, monkeypatch):
    # Arrange
    # половина настроек — тоже выключено, иначе запрос ушёл бы в никуда
    monkeypatch.setattr(settings, "TELEGRAM_FEEDBACK_BOT_TOKEN", "test-token")
    monkeypatch.setattr(settings, "TELEGRAM_FEEDBACK_CHAT_ID", None)

    user = User(id=3, email="user@test.com")

    # Act
    await notify_new_feedback(make_feedback(), user)

    # Assert
    assert fake_client == []


@pytest.mark.asyncio
async def test_message_contains_feedback_details(fake_client, telegram_configured):
    # Arrange
    user = User(id=3, email="user@test.com")
    feedback = make_feedback(
        id=17,
        topic="bug",
        message="Кнопка запуска бота не реагирует на клик",
        email="answer@test.com",
        rating=2,
    )

    # Act
    await notify_new_feedback(feedback, user)

    # Assert
    assert len(fake_client) == 1
    url, payload = fake_client[0]

    assert "test-token" in url
    assert payload["chat_id"] == "-100500"

    text = payload["text"]
    assert "#17" in text
    assert "Баг" in text
    assert "2/5" in text
    assert "user@test.com" in text  # чей аккаунт
    assert "answer@test.com" in text  # куда отвечать
    assert "Кнопка запуска бота не реагирует на клик" in text

    # разметку не включаем — текст отзыва пишет пользователь
    assert "parse_mode" not in payload


@pytest.mark.asyncio
async def test_optional_lines_skipped(fake_client, telegram_configured):
    # Arrange
    user = User(id=3, email="user@test.com")
    feedback = make_feedback(rating=None, email=None)

    # Act
    await notify_new_feedback(feedback, user)

    # Assert
    text = fake_client[0][1]["text"]
    assert "Оценка" not in text
    assert "Email для ответа" not in text


@pytest.mark.asyncio
async def test_long_message_truncated(fake_client, telegram_configured):
    # Arrange
    # 2000 символов текста (максимум по схеме) плюс шапка должны влезать в лимит Telegram
    user = User(id=3, email="user@test.com")
    feedback = make_feedback(message="а" * 2000)

    # Act
    await notify_new_feedback(feedback, user)

    # Assert
    assert len(fake_client[0][1]["text"]) <= feedback_notifier.MAX_MESSAGE_LENGTH


@pytest.mark.asyncio
async def test_telegram_failure_is_swallowed(monkeypatch, telegram_configured):
    # Arrange
    # отзыв уже сохранён в БД — падение Telegram не должно превратиться в ошибку ответа
    monkeypatch.setattr(httpx, "AsyncClient", BrokenAsyncClient)

    user = User(id=3, email="user@test.com")

    # Act / Assert
    # именно отсутствие исключения здесь и есть проверяемое поведение
    await notify_new_feedback(make_feedback(), user)
