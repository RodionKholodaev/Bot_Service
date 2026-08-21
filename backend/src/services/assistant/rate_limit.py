"""Ограничение частоты обращений к ИИ-ассистенту.

Каждый вызов модели стоит денег (см. docs/ai-assistant/README.md, раздел
«Стоимость»), а эндпоинт закрыт только авторизацией. Без лимита один
пользователь может крутить платные запросы сколько угодно — расход упирается
разве что в его терпение.

Два скользящих окна сразу: минутное гасит спам подряд, суточное держит дневной
расход на пользователя. Окна именно скользящие, а не календарные — иначе лимит
рывком обнулялся бы в полночь, и это ровно тот момент, когда его удобно обходить.

Хранилище — обычная таблица assistant_requests, без Redis: бэкенд и так живёт
одним процессом (см. CLAUDE.md), а отдельная инфраструктура ради счётчика тут
не нужна. Тот же приём уже используется в services/feedback_service.py.
"""

import logging
from datetime import UTC, datetime, timedelta

from src.core.exceptions import TooManyRequestsError
from src.repositories.assistant_request_repository import AssistantRequestRepository

logger = logging.getLogger(__name__)

# Сколько запросов к ассистенту разрешено одному пользователю.
ASSISTANT_LIMIT_PER_MINUTE = 10
ASSISTANT_LIMIT_PER_DAY = 100


class AssistantRateLimiter:
    def __init__(self, repo):
        self.repo: AssistantRequestRepository = repo

    async def check_and_register(self, user) -> None:
        """Пропускает запрос и отмечает его, либо бросает TooManyRequestsError."""
        now = datetime.now(UTC)

        minute_count = await self.repo.count_since(user.id, now - timedelta(minutes=1))
        if minute_count >= ASSISTANT_LIMIT_PER_MINUTE:
            self._reject(
                user_id=user.id,
                window="minute",
                count=minute_count,
                detail=(
                    f"Слишком много запросов к ИИ-помощнику: не больше "
                    f"{ASSISTANT_LIMIT_PER_MINUTE} в минуту. Подождите немного и повторите."
                ),
            )

        day_count = await self.repo.count_since(user.id, now - timedelta(days=1))
        if day_count >= ASSISTANT_LIMIT_PER_DAY:
            self._reject(
                user_id=user.id,
                window="day",
                count=day_count,
                detail=(
                    f"Исчерпан дневной лимит ИИ-помощника: {ASSISTANT_LIMIT_PER_DAY} запросов. "
                    "Лимит считается за последние 24 часа — попробуйте позже."
                ),
            )

        # Отмечаем запрос ДО обращения к модели: если писать после ответа,
        # параллельные запросы одного пользователя проскочат мимо счётчика,
        # а прерванный ответ вообще не будет учтён.
        await self.repo.create(user.id)

    @staticmethod
    def _reject(*, user_id: int, window: str, count: int, detail: str) -> None:
        logger.info(
            "Assistant rate limit exceeded",
            extra={"user_id": user_id, "window": window, "recent_count": count},
        )
        raise TooManyRequestsError(detail)
