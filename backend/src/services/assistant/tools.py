"""Инструменты, которые ассистент может вызвать во время ответа.

Два инструмента:

- ``suggest_settings`` — модель предлагает конкретные значения полей формы.
  Ничего не выполняет: значения валидируются и уходят на фронт, где пользователь
  применяет их кнопкой. Всё, что модель придумала сверх схемы, отбрасывается.
- ``web_search`` — запрос в perplexity sonar через тот же AITunnel. Sonar сам ходит
  в интернет и возвращает ответ со ссылками.
"""

import json
import logging
from typing import Any

import httpx

from src.config import settings
from src.services.assistant import aitunnel

logger = logging.getLogger(__name__)

# Поля формы, которые ассистенту разрешено предлагать.
# Ключ — имя поля в formData на фронте, значение — человекочитаемая подпись
# (используется только в логах, фронт рисует свои подписи).
SUGGESTABLE_FIELDS: dict[str, str] = {
    "dryRun": "Режим торговли",
    "stakeAmount": "Депозит бота",
    "balanceRatio": "Размер сделки, %",
    "tradingPair": "Торговая пара",
    "leverage": "Плечо",
    "algorithm": "Направление",
    "strategyPreset": "Пресет стратегии",
    "filters": "Условия входа",
    "botName": "Имя бота",
    "takeProfit": "Take Profit, %",
    "useStopLoss": "Использовать Stop Loss",
    "stopLoss": "Stop Loss, %",
}

_INDICATORS = {"rsi", "cci"}
_TIMEFRAMES = {"1m", "5m", "15m", "30m", "1h", "4h"}
_CONDITIONS = {"less", "greater"}
_PRESETS = {"conservative", "moderate", "aggressive", "custom"}

SUGGEST_SETTINGS_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "suggest_settings",
        "description": (
            "Предложить пользователю конкретные значения полей формы создания бота. "
            "Пользователь увидит их карточкой и применит одной кнопкой. "
            "Вызывай всегда, когда советуешь конкретные числа или параметры. "
            "Предлагай только то, что реально меняешь — не дублируй уже стоящие значения."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "suggestions": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 8,
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {
                                "type": "string",
                                "enum": list(SUGGESTABLE_FIELDS.keys()),
                                "description": (
                                    "Поле формы. filters — массив условий входа; "
                                    "если предлагаешь filters, форма автоматически "
                                    "переключится в режим «Свои настройки»."
                                ),
                            },
                            "value": {
                                "description": (
                                    "Значение. Числа (stakeAmount, balanceRatio, leverage, "
                                    "takeProfit, stopLoss) — числом. dryRun/useStopLoss — true/false. "
                                    "tradingPair — строка вида BTC/USDT. algorithm — long или short. "
                                    "strategyPreset — conservative/moderate/aggressive/custom. "
                                    "filters — массив объектов "
                                    "{indicator: rsi|cci, timeframe: 1m|5m|15m|30m|1h|4h, "
                                    "condition: less|greater, value: число}."
                                ),
                            },
                            "reason": {
                                "type": "string",
                                "description": "Одно короткое предложение: почему именно это значение.",
                            },
                        },
                        "required": ["field", "value", "reason"],
                    },
                }
            },
            "required": ["suggestions"],
        },
    },
}

WEB_SEARCH_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Найти актуальную информацию в интернете: текущий курс монеты, новости, "
            "недавние события рынка. Не используй для вопросов об устройстве самого сервиса."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Поисковый запрос простыми словами.",
                }
            },
            "required": ["query"],
        },
    },
}

# вставки иформации о инструментах
def build_tools(web_search_enabled: bool) -> list[dict[str, Any]]:
    tools = [SUGGEST_SETTINGS_TOOL]
    if web_search_enabled:
        tools.append(WEB_SEARCH_TOOL)
    return tools


# ── Валидация предложений ────────────────────────────────────────────────

# аккуратное преобразование в число
def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().replace(",", "."))
        except ValueError:
            return None
    return None


def _clean_filters(value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(value, list) or not value:
        return None
    cleaned: list[dict[str, Any]] = []
    for raw in value[:12]:
        if not isinstance(raw, dict):
            continue
        indicator = str(raw.get("indicator", "")).lower()
        timeframe = str(raw.get("timeframe", "")).lower()
        condition = str(raw.get("condition", "")).lower()
        number = _as_number(raw.get("value"))
        if indicator not in _INDICATORS or timeframe not in _TIMEFRAMES:
            continue
        if condition not in _CONDITIONS or number is None:
            continue
        cleaned.append(
            {
                "indicator": indicator,
                "timeframe": timeframe,
                "condition": condition,
                "value": number,
            }
        )
    return cleaned or None


def _normalize_value(field: str, value: Any) -> Any:
    """Приводит значение к тому виду, в котором его хранит formData на фронте.

    Числовые поля формы хранятся строками (это обычные <input>), поэтому числа
    возвращаются строками. Невалидное значение — None, такое предложение отбрасывается.
    """
    if field in ("dryRun", "useStopLoss"):
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return value.lower() == "true"
        return None

    if field == "filters":
        return _clean_filters(value)

    if field == "tradingPair":
        pair = str(value).strip().upper()
        return pair if "/" in pair and 5 <= len(pair) <= 30 else None

    if field == "algorithm":
        direction = str(value).strip().lower()
        return direction if direction in ("long", "short") else None

    if field == "strategyPreset":
        preset = str(value).strip().lower()
        return preset if preset in _PRESETS else None

    if field == "botName":
        name = str(value).strip()
        return name[:100] if name else None

    if field == "leverage":
        number = _as_number(value)
        if number is None or not 1 <= number <= 20:
            return None
        return str(int(number))

    if field == "balanceRatio":
        number = _as_number(value)
        if number is None or not 5 <= number <= 100:
            return None
        return str(int(round(number / 5) * 5))  # ползунок ходит с шагом 5

    if field == "stakeAmount":
        number = _as_number(value)
        if number is None or number <= 0:
            return None
        return str(int(number)) if number.is_integer() else str(round(number, 2))

    if field in ("takeProfit", "stopLoss"):
        number = _as_number(value)
        if number is None or not 0 < number <= 100:
            return None
        return str(round(number, 2)).rstrip("0").rstrip(".")

    return None


def normalize_suggestions(raw_arguments: str) -> list[dict[str, Any]]:
    """Разбирает аргументы вызова suggest_settings и оставляет только валидное."""
    try:
        parsed = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError:
        logger.warning(
            "Assistant sent malformed suggest_settings arguments",
            extra={"raw_arguments": (raw_arguments or "")[:200]},
        )
        return []

    items = parsed.get("suggestions")
    if not isinstance(items, list):
        return []

    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items[:8]:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field", ""))
        if field not in SUGGESTABLE_FIELDS or field in seen:
            continue
        value = _normalize_value(field, item.get("value"))
        if value is None:
            logger.info(
                "Dropped invalid assistant suggestion",
                extra={"field": field, "raw_value": str(item.get("value"))[:120]},
            )
            continue
        seen.add(field)
        result.append(
            {
                "field": field,
                "value": value,
                "reason": str(item.get("reason", "")).strip()[:300],
            }
        )
    return result


# ── Веб-поиск ────────────────────────────────────────────────────────────


async def run_web_search(client: httpx.AsyncClient, query: str) -> tuple[str, list[str]]:
    """Возвращает (текст ответа для модели, список ссылок-источников)."""
    response = await aitunnel.complete(
        client,
        model=settings.AI_SEARCH_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Отвечай кратко и фактически, на русском. "
                    "Всегда указывай дату/время актуальности данных, если это цена или новость."
                ),
            },
            {"role": "user", "content": query},
        ],
        max_tokens=800,
        temperature=0.2,
    )

    choices = response.get("choices") or []
    content = ""
    if choices:
        content = (choices[0].get("message") or {}).get("content") or ""

    # sonar кладёт ссылки в citations рядом с choices; у части моделей их нет вовсе
    citations = response.get("citations") or []
    sources = [str(url) for url in citations if isinstance(url, str)][:6]

    if not content:
        content = "Поиск не дал результата."

    return content, sources
