"""ИИ-ассистент страницы создания бота.

Разбит на четыре независимых куска, чтобы каждый можно было править отдельно:

- ``aitunnel.py``    — транспорт: HTTP к api.aitunnel.ru (OpenAI-совместимый).
- ``prompt.py``      — системный промпт и рендер снимка формы.
- ``tools.py``       — инструменты модели (веб-поиск, предложение настроек).
- ``service.py``     — агентный цикл: стриминг + вызовы инструментов.
"""

from src.services.assistant.service import AssistantService, assistant_enabled

__all__ = ["AssistantService", "assistant_enabled"]
