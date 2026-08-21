"""ИИ-ассистент страницы создания бота.

Разбит на четыре независимых куска, чтобы каждый можно было править отдельно:

- ``aitunnel.py``    — транспорт: HTTP к api.aitunnel.ru (OpenAI-совместимый).
- ``prompt.py``      — системный промпт и рендер снимка формы.
- ``tools.py``       — инструменты модели (веб-поиск, предложение настроек).
- ``service.py``     — агентный цикл: стриминг + вызовы инструментов.
- ``rate_limit.py``  — сколько запросов в минуту и в сутки можно одному пользователю.
"""

from src.services.assistant.rate_limit import AssistantRateLimiter
from src.services.assistant.service import AssistantService, assistant_enabled

__all__ = ["AssistantRateLimiter", "AssistantService", "assistant_enabled"]
