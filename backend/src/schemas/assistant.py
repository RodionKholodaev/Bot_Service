"""Схемы запроса/ответа ИИ-ассистента на странице создания бота.

Поля BotFormSnapshot намеренно названы в camelCase — это дословный снимок
объекта formData из frontend/app/bot-creation/page.tsx. Так ассистент видит
ровно то же, что видит пользователь, а подсказки (suggestions) возвращаются
с теми же именами полей и применяются на фронте без маппинга.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Одно сообщение диалога. Историю хранит фронт и присылает целиком."""

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=8000)


class BotFormSnapshot(BaseModel):
    """Текущее состояние мастера создания бота."""

    step: int = Field(default=1, ge=1, le=4)

    # Шаг 1 — режим, депозит
    dryRun: bool = True
    stakeAmount: str | None = None
    balanceRatio: str | None = None
    hasApiKeys: bool = False

    # Шаг 2 — пара, плечо, направление
    tradingPair: str | None = None
    leverage: str | None = None
    algorithm: str | None = None

    # Шаг 3 — стратегия входа
    strategyPreset: str | None = None
    filters: list[dict[str, Any]] = Field(default_factory=list, max_length=30)

    # Шаг 4 — имя и выход из сделки
    botName: str | None = None
    takeProfit: str | None = None
    useStopLoss: bool = False
    stopLoss: str | None = None


class AssistantChatRequest(BaseModel):
    """Тело POST /assistant/chat."""

    # История общения
    # Последнее сообщение в списке — текущий вопрос пользователя.
    # [
    # {role: "user",      content: "какое плечо поставить?"},
    # {role: "assistant", content: "для BTC/USDT на споте обычно берут x2–x5..."},
    # {role: "user",      content: "а если агрессивнее?"},
    # ...
    # ]
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=40)
    # То что сейчас стоит в форме создания бота
    form: BotFormSnapshot = Field(default_factory=BotFormSnapshot)

    # Разрешить ассистенту ходить в интернет (тумблер в панели).
    web_search: bool = False


class AssistantStatus(BaseModel):
    """Ответ GET /assistant/status — включён ли ассистент на этом сервере."""

    enabled: bool
    web_search_available: bool
