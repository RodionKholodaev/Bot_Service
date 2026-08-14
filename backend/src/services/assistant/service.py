"""Агентный цикл ассистента.

Один вызов ``AssistantService.stream()`` = один ответ пользователю. Внутри может
быть несколько обращений к модели: если модель попросила инструмент, мы его
выполняем, дописываем результат в диалог и просим модель продолжить.

Наружу отдаётся поток событий (обычные dict), которые роутер заворачивает в SSE:

    {"type": "status",      "stage": "thinking" | "searching", "query": str}
    {"type": "delta",       "text": "кусок ответа"}
    {"type": "suggestions", "items": [{"field", "value", "reason"}, ...]}
    {"type": "sources",     "items": ["https://...", ...]}
    {"type": "error",       "message": "текст для пользователя"}
    {"type": "done"}
"""

import json
import logging
from typing import Any, AsyncIterator

from src.config import settings
from src.schemas.assistant import AssistantChatRequest
from src.services.assistant import aitunnel, prompt, tools
from src.services.assistant.aitunnel import AITunnelError

logger = logging.getLogger(__name__)

# Сколько раз подряд модель может вызвать инструменты, прежде чем мы её остановим.
MAX_TOOL_ROUNDS = 3


def assistant_enabled() -> bool:
    """Ассистент работает, только если задан ключ AITunnel."""
    return bool(settings.AITUNNEL_API_KEY)


class AssistantService:
    def __init__(self, user_id: Any | None = None):
        self.user_id = user_id

    async def stream(self, request: AssistantChatRequest) -> AsyncIterator[dict[str, Any]]:
        # история диалога:
        # пользователь: его реплика
        # нейросеть: его реплика
        # и тд
        history = [{"role": m.role, "content": m.content} for m in request.messages]
        # правила (системный промт) + снимок формы + диалог
        messages = prompt.build_messages(request.form, history)
        # добавляем инструменты для работы с интернетом если request.web_search == True
        tool_schemas = tools.build_tools(request.web_search)

        logger.info(
            "Assistant request started",
            extra={
                "user_id": self.user_id,
                "step": request.form.step,
                "web_search": request.web_search,
                "history_len": len(history),
            },
        )

        try:
            # открытие клиента с нужными настройками
            async with aitunnel.build_client() as client:
                for round_index in range(MAX_TOOL_ROUNDS):
                    # перед обращением к модели отправляем статус: думаю, чтобы отобразить в ui
                    yield {"type": "status", "stage": "thinking"}

                    sink: dict[str, Any] = {}
                    async for event in self._stream_round(client, messages, tool_schemas, sink):
                        yield event

                    calls = self._collect_tool_calls(sink)
                    if not calls:
                        break

                    # Последний раунд — инструменты больше не выполняем, иначе зациклимся.
                    if round_index == MAX_TOOL_ROUNDS - 1:
                        logger.warning(
                            "Assistant hit tool-round limit",
                            extra={"user_id": self.user_id, "rounds": MAX_TOOL_ROUNDS},
                        )
                        break

                    messages.append(self._assistant_turn(sink, calls))
                    for call in calls:
                        async for event in self._run_tool(client, call, messages):
                            yield event
        except AITunnelError:
            logger.exception("Assistant provider call failed", extra={"user_id": self.user_id})
            yield {
                "type": "error",
                "message": "Не удалось получить ответ от ИИ. Попробуйте ещё раз.",
            }
        except Exception:
            logger.exception("Assistant request crashed", extra={"user_id": self.user_id})
            yield {"type": "error", "message": "Внутренняя ошибка ассистента."}

        yield {"type": "done"}

    # ── Один раунд общения с моделью ─────────────────────────────────────

    async def _stream_round(
        self,
        client,
        # уже имеющиеся сообщения
        messages: list[dict[str, Any]],
        # список инструментов, котоыре нейросеть может запрашивать
        tool_schemas: list[dict[str, Any]],
        # место куда функция будет складывать то что получила от нейросети
        sink: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        """Стримит ответ модели, складывая текст и вызовы инструментов в ``sink``."""
        # создаем места для ответа нейросети и инструментов, которые нейросеть просит вызвать
        sink["content"] = ""
        sink["tool_calls"] = {}

        # ассинхроные вариант for
        # отправляем запрос в нейросеть
        # говорим какие tools она может использовать, передаем сообщения и модель
        async for chunk in aitunnel.stream_chat_completion(
            client,
            model=settings.AI_ASSISTANT_MODEL,
            messages=messages,
            tools=tool_schemas,
        ):
            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}

            piece = delta.get("content")
            if piece:
                sink["content"] += piece
                yield {"type": "delta", "text": piece}

            # Аргументы инструмента приходят по кускам — склеиваем по index.
            for call in delta.get("tool_calls") or []:
                index = call.get("index", 0)
                slot = sink["tool_calls"].setdefault(index, {"id": "", "name": "", "arguments": ""})
                if call.get("id"):
                    slot["id"] = call["id"]
                function = call.get("function") or {}
                if function.get("name"):
                    slot["name"] = function["name"]
                if function.get("arguments"):
                    slot["arguments"] += function["arguments"]

    @staticmethod
    def _collect_tool_calls(sink: dict[str, Any]) -> list[dict[str, str]]:
        calls = sink.get("tool_calls") or {}
        return [call for _, call in sorted(calls.items()) if call.get("name")]

    @staticmethod
    def _assistant_turn(sink: dict[str, Any], calls: list[dict[str, str]]) -> dict[str, Any]:
        """Ход ассистента с вызовами инструментов — в формате, который ждёт API."""
        return {
            "role": "assistant",
            "content": sink.get("content") or None,
            "tool_calls": [
                {
                    "id": call["id"] or f"call_{index}",
                    "type": "function",
                    "function": {"name": call["name"], "arguments": call["arguments"] or "{}"},
                }
                for index, call in enumerate(calls)
            ],
        }

    # ── Выполнение инструментов ──────────────────────────────────────────

    async def _run_tool(
        self, client, call: dict[str, str], messages: list[dict[str, Any]]
    ) -> AsyncIterator[dict[str, Any]]:
        name = call["name"]
        call_id = call["id"] or f"call_{name}"

        if name == "suggest_settings":
            items = tools.normalize_suggestions(call["arguments"])
            if items:
                yield {"type": "suggestions", "items": items}
            result = (
                f"Пользователю показаны предложения по полям: "
                f"{', '.join(item['field'] for item in items)}. "
                "Теперь коротко объясни выбор."
                if items
                else "Ни одно предложение не прошло валидацию — не повторяй вызов, объясни словами."
            )
            messages.append({"role": "tool", "tool_call_id": call_id, "content": result})
            return

        if name == "web_search":
            query = self._extract_query(call["arguments"])
            yield {"type": "status", "stage": "searching", "query": query}
            try:
                answer, sources = await tools.run_web_search(client, query)
            except AITunnelError:
                logger.exception("Web search failed", extra={"user_id": self.user_id, "query": query})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": "Поиск недоступен. Ответь по своим знаниям и предупреди об этом.",
                    }
                )
                return
            if sources:
                yield {"type": "sources", "items": sources}
            messages.append({"role": "tool", "tool_call_id": call_id, "content": answer})
            return

        logger.warning(
            "Assistant called unknown tool", extra={"tool": name, "user_id": self.user_id}
        )
        messages.append(
            {"role": "tool", "tool_call_id": call_id, "content": "Такого инструмента нет."}
        )

    @staticmethod
    def _extract_query(raw_arguments: str) -> str:
        try:
            return str((json.loads(raw_arguments or "{}")).get("query", ""))[:300]
        except json.JSONDecodeError:
            return ""
