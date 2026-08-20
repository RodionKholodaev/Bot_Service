"""Тонкий клиент AITunnel (https://aitunnel.ru).

AITunnel — OpenAI-совместимый агрегатор, поэтому здесь обычный
POST /chat/completions: и стриминг (SSE), и tool calling в формате OpenAI.
Отдельная SDK не нужна — httpx уже есть в зависимостях.
"""

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class AITunnelError(RuntimeError):
    """Ошибка на стороне провайдера моделей (сеть, ключ, лимиты, 5xx)."""


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.AITUNNEL_API_KEY}",
        "Content-Type": "application/json",
    }


def _url(path: str) -> str:
    return f"{settings.AITUNNEL_BASE_URL.rstrip('/')}{path}"


async def complete(
    client: httpx.AsyncClient,
    *,
    model: str,
    messages: list[dict[str, Any]],
    max_tokens: int = 1024,
    temperature: float = 0.3,
) -> dict[str, Any]:
    """Обычный (нестриминговый) запрос. Используется для веб-поиска."""
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    try:
        response = await client.post(_url("/chat/completions"), headers=_headers(), json=payload)
    except httpx.HTTPError as exc:
        raise AITunnelError(f"request to AITunnel failed: {exc}") from exc

    if response.status_code >= 400:
        raise AITunnelError(f"AITunnel returned {response.status_code}: {response.text[:500]}")

    return response.json()


async def stream_chat_completion(
    client: httpx.AsyncClient,
    *,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    max_tokens: int = 1400,
    temperature: float = 0.4,
) -> AsyncIterator[dict[str, Any]]:
    """Стримит ответ модели, отдавая уже распарсенные SSE-чанки OpenAI-формата.

    Служебный кадр ``data: [DONE]`` и некорректный JSON молча пропускаются —
    отдельные провайдеры любят присылать keep-alive комментарии.
    """
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    try:
        async with client.stream("POST", _url("/chat/completions"), headers=_headers(), json=payload) as response:
            if response.status_code >= 400:
                body = (await response.aread()).decode("utf-8", errors="replace")
                raise AITunnelError(f"AITunnel returned {response.status_code}: {body[:500]}")

            async for line in response.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if not data or data == "[DONE]":
                    continue
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    logger.warning("Skipped malformed SSE chunk from AITunnel", extra={"chunk": data[:200]})
    except httpx.HTTPError as exc:
        raise AITunnelError(f"stream from AITunnel failed: {exc}") from exc


def build_client() -> httpx.AsyncClient:
    """AsyncClient с таймаутом из настроек. Создаётся на один диалог."""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(settings.AI_ASSISTANT_TIMEOUT, connect=15.0),
    )
