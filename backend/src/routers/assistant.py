"""HTTP-слой ИИ-ассистента: SSE-стрим ответа и проверка доступности."""

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from src.core.dependencies import get_current_user
from src.core.exceptions import BadRequestError
from src.models.user import User
from src.schemas.assistant import AssistantChatRequest, AssistantStatus
from src.services.assistant import AssistantService, assistant_enabled

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.get("/status", response_model=AssistantStatus)
async def status(current_user: User = Depends(get_current_user)) -> AssistantStatus:
    """Фронт спрашивает при монтировании страницы: показывать ли панель ассистента."""
    return AssistantStatus(enabled=assistant_enabled(), web_search_available=assistant_enabled())


@router.post("/chat")
async def chat(
    request: AssistantChatRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Ответ ассистента одним SSE-потоком. (Server-Sent Events - протокол для стриминга поверх HTTP)

    Каждое событие — строка ``data: {...}``; типы событий описаны в
    ``services/assistant/service.py``. Соединение закрывается после ``done``.
    """
    # проверка, есть ли на сервере ключ для доступа к нейросети
    if not assistant_enabled():
        raise BadRequestError("ИИ-ассистент не настроен на сервере")

    service = AssistantService(user_id=current_user.id)

    # генератор для постепенной отдачи ответа от нейросети
    async def event_stream() -> AsyncIterator[str]:
        async for event in service.stream(request):
            # превращаем данные в json строку для отправки
            # стандартный формат для SSE
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    # кусочкаси отдаем ответ на фронт
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            # запрещаем кеширование и преобразование данных
            "Cache-Control": "no-cache, no-transform",
            # не закрывать соединение после ответа, ведь данные еще будут идти
            "Connection": "keep-alive",
            # Отключает буферизацию у nginx — иначе стрим приедет одним куском.
            "X-Accel-Buffering": "no",
        },
    )
