# Рецепты доработки ИИ-помощника

Типовые задачи по шагам. Устройство системы — в [backend.md](backend.md)
и [frontend.md](frontend.md).

---

## Оглавление

- [Добавить поле формы, которое помощник умеет предлагать](#добавить-поле-формы-которое-помощник-умеет-предлагать)
- [Добавить новый инструмент модели](#добавить-новый-инструмент-модели)
- [Поменять модель или провайдера](#поменять-модель-или-провайдера)
- [Поменять тон и правила ответов](#поменять-тон-и-правила-ответов)
- [Поменять быстрые вопросы](#поменять-быстрые-вопросы)
- [Поменять внешний вид панели](#поменять-внешний-вид-панели)
- [Ограничить длину истории и расход](#как-удешевить-работу-помощника)
- [Прогнать агентный цикл без реальных запросов](#прогнать-агентный-цикл-без-реальных-запросов)
- [Отладка: симптом → причина](#отладка-симптом--причина)

---

## Добавить поле формы, которое помощник умеет предлагать

Пример: в форме появился `trailingStop` (галочка «Трейлинг стоп», уже есть
в `formData`, но помощнику недоступна).

### 1. Бэкенд: разрешить поле

`backend/src/services/assistant/tools.py`:

```python
SUGGESTABLE_FIELDS: dict[str, str] = {
    ...
    "trailingStop": "Трейлинг стоп",   # ← добавить
}
```

Enum в схеме инструмента строится из этого словаря автоматически — модель сразу
увидит новое имя.

### 2. Бэкенд: описать валидацию

Там же, в `_normalize_value()`:

```python
if field in ("dryRun", "useStopLoss", "trailingStop"):   # ← дописать в булев блок
    ...
```

Для числового поля — свой блок с диапазоном, по образцу `leverage`. **Помните
про формат:** числа возвращаются строками, потому что `formData` хранит их
строками.

### 3. Бэкенд: рассказать модели

`backend/src/services/assistant/prompt.py`, `SYSTEM_PROMPT`, раздел нужного шага:

```
- Трейлинг стоп — стоп-лосс едет за ценой, сохраняя дистанцию. Работает только
  вместе с включённым Stop Loss.
```

**Этот шаг пропускать нельзя.** Поле, разрешённое в схеме, но не описанное
в промпте, модель либо не использует, либо использует неправильно.

### 4. Фронтенд: подпись и формат

`frontend/app/bot-creation/assistant/types.ts`:

```ts
export type SuggestableField = ... | 'trailingStop';
```

`fieldMeta.ts`:

```ts
trailingStop: {
  label: 'Трейлинг стоп',
  step: 4,
  format: (v) => (v ? 'Включить' : 'Выключить'),
},
```

### 5. Фронтенд: связанные поля (если нужны)

`applySuggestions.ts` — если поле тянет за собой другое. Для трейлинга это так:

```ts
case 'trailingStop':
  next = { ...next, trailingStop: Boolean(suggestion.value), useStopLoss: true };
  break;
```

Без этого галочка встанет, но форма покажет её только при включённом Stop Loss.

### 6. Тест

`backend/tests/unit/test_assistant_suggestions.py` — добавьте случай с граничным
или мусорным значением. Файл специально держится маленьким и однотипным.

```bash
cd backend && python -m pytest tests/unit/test_assistant_suggestions.py -v
```

---

## Добавить новый инструмент модели

Пример: инструмент `get_pair_price`, который тянет текущую цену пары.

### 1. Схема инструмента

`tools.py`, рядом с `WEB_SEARCH_TOOL`:

```python
GET_PAIR_PRICE_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_pair_price",
        "description": "Текущая цена торговой пары. Используй, когда пользователь "
                       "спрашивает про цену выбранной пары.",
        "parameters": {
            "type": "object",
            "properties": {"pair": {"type": "string", "description": "Например BTC/USDT"}},
            "required": ["pair"],
        },
    },
}
```

И в `build_tools()`:

```python
def build_tools(web_search_enabled: bool) -> list[dict[str, Any]]:
    tools = [SUGGEST_SETTINGS_TOOL, GET_PAIR_PRICE_TOOL]
    if web_search_enabled:
        tools.append(WEB_SEARCH_TOOL)
    return tools
```

### 2. Исполнитель

Там же — обычная async-функция, возвращающая текст для модели:

```python
async def run_get_pair_price(client: httpx.AsyncClient, pair: str) -> str:
    ...
```

### 3. Ветка в агентном цикле

`service.py`, `_run_tool()`:

```python
if name == "get_pair_price":
    pair = self._extract_arg(call["arguments"], "pair")
    yield {"type": "status", "stage": "thinking"}       # или своё событие
    try:
        result = await tools.run_get_pair_price(client, pair)
    except Exception:
        logger.exception("Price lookup failed", extra={"pair": pair})
        result = "Цену получить не удалось, ответь по своим знаниям."
    messages.append({"role": "tool", "tool_call_id": call_id, "content": result})
    return
```

Обязательное правило: **на каждый вызов инструмента должен быть ровно один
`{"role": "tool", ...}` в `messages`**, даже если инструмент упал. Иначе провайдер
вернёт ошибку о несоответствии `tool_call_id`.

`_extract_query` сейчас достаёт только поле `query`; для новых инструментов
сделайте общий `_extract_arg(raw, name)` по тому же образцу.

### 4. Если нужно новое событие для UI

- тип в `frontend/.../types.ts` → `AssistantEvent`;
- ветка в `switch` внутри `useAssistantChat.send`;
- отрисовка в нужном компоненте.

### 5. Упомянуть в промпте

`prompt.py`, раздел «Инструменты» — когда его использовать, а когда нет.
Без этого модель будет звать инструмент невпопад или не звать вовсе.

---

## Поменять модель или провайдера

### Другая модель на AITunnel

Только `.env`:

```env
AI_ASSISTANT_MODEL=claude-sonnet-4-5
```

Код от модели не зависит. Единственное жёсткое требование — **поддержка tool
calling**. Без неё не будет ни предложений настроек, ни веб-поиска: помощник
превратится в обычный чат.

Проверять после смены: задайте «посоветуй настройки для этого бота» и убедитесь,
что появилась карточка с кнопкой «Применить», а не список чисел текстом.

### Другой провайдер

Если у него OpenAI-совместимый API — достаточно `AITUNNEL_BASE_URL` и ключа.
Если нет — переписывается один файл, `services/assistant/aitunnel.py`; всё
остальное работает с его функциями, а не с HTTP напрямую.

### Модель веб-поиска

`AI_SEARCH_MODEL`. Учтите: ссылки достаются из поля `citations` в ответе
(так делает perplexity sonar). У другой модели их может не быть — тогда ответ
придёт без источников, ошибки не будет, но чипы со ссылками пропадут.
Место правки — `run_web_search()` в `tools.py`.

---

## Поменять тон и правила ответов

`backend/src/services/assistant/prompt.py`, константа `SYSTEM_PROMPT`.

Что там особенно важно и что не стоит выкидывать:

| Блок | Зачем нужен |
|---|---|
| «аудитория — не программисты» | Иначе ответы уходят в жаргон |
| Полный перечень полей с диапазонами | Модель не предложит плечо x50, которого нет в форме |
| **Список того, чего в продукте нет** | Без него модель бодро советует MACD, стоп-трейлинг-стратегии и Binance Spot |
| «вызывай suggest_settings вместо чисел текстом» | Иначе фича «применить одной кнопкой» просто не срабатывает |
| «не предлагай то, что уже стоит в форме» | Иначе половина карточки — предложения ничего не менять |
| «не обещай прибыль, не давай инвестсоветов» | Продукт финансовый, это не косметика |

После правок промпта прогоняйте один и тот же набор вопросов («посоветуй настройки»,
«как снизить риск», «что такое RSI», «добавь MACD») — регрессии видно сразу.

---

## Поменять быстрые вопросы

`frontend/app/bot-creation/assistant/WelcomeState.tsx`, словарь `PROMPTS_BY_STEP`:
свой список на каждый шаг мастера, по 3 штуки — больше не помещается аккуратно.

---

## Поменять внешний вид панели

Всё в `frontend/app/bot-creation/assistant/assistant.css`.

| Что | Где |
|---|---|
| Ширина панели | `--ai-width` в `:root` |
| Точка перехода «сдвиг ↔ overlay» | Медиазапросы `min-width: 1180px` / `max-width: 1179px` — менять **оба** |
| Цвета | Токены `--ai-bg`, `--ai-accent`, `--ai-line`, `--ai-text`, `--ai-muted`, `--ai-dim` на `.ai-panel, .ai-launcher` |
| Вкладка-открывашка | `.ai-launcher__tab`, подпись — `.ai-launcher__label` (`writing-mode`) |
| Разовая подсказка | `.ai-launcher__hint`, тайминги — в `AssistantLauncher.tsx` |
| Скорость выезда | `transition` у `.ai-panel` и `.create-bot-page` — держите их одинаковыми, иначе панель и форма разъедутся |

Если меняете ширину — проверьте обе раскладки: на широком экране форма должна
остаться целиком видимой, на узком панель должна лечь поверх с затемнением.

---

## Как удешевить работу помощника

По убыванию эффекта:

1. **Обрезать историю.** Сейчас на бэкенд уходит весь диалог (до 40 сообщений).
   Проще всего резать на фронте, в `useAssistantChat.send`:

   ```ts
   const history = [...messagesRef.current, userMessage]
     .slice(-12)                       // последние 6 пар вопрос-ответ
     .map(({ role, content }) => ({ role, content }));
   ```

2. **Взять модель подешевле** — `AI_ASSISTANT_MODEL`. Задача несложная,
   mini-класса обычно хватает.

3. **Уменьшить `max_tokens`** в `aitunnel.stream_chat_completion` (по умолчанию
   1400). Ответы и так просят делать короткими.

4. **Сократить `SYSTEM_PROMPT`** — он уходит с каждым сообщением. Но не за счёт
   списка «чего в продукте нет»: сэкономите токены, получите неверные советы.

5. **Выключить веб-поиск по умолчанию** — уже так: тумблер выключен, каждый поиск
   это отдельный платный запрос к `sonar`.

Если понадобится жёсткий лимит на пользователя — самое естественное место
`routers/assistant.py`, перед созданием `AssistantService`: счётчик запросов
в памяти или в БД по `current_user.id`.

---

## Прогнать агентный цикл без реальных запросов

Тестов на цикл нет — там всё интересное в разговоре с внешним сервисом. Но
подменить провайдера просто: в `service.py` обращения идут через модуль
`aitunnel`, а не через httpx напрямую.

Скрипт-заготовка (положите куда-нибудь во временную папку, запускайте из `backend/`):

```python
import asyncio, json, sys
sys.path.insert(0, ".")

from src.services.assistant import aitunnel, service as service_mod, tools as tools_mod
from src.schemas.assistant import AssistantChatRequest

ROUNDS = []

async def fake_stream(client, *, model, messages, tools=None, **kw):
    step = len(ROUNDS); ROUNDS.append(step)
    if step == 0:
        # модель зовёт suggest_settings, аргументы приходят двумя кусками
        yield {"choices": [{"delta": {"tool_calls": [
            {"index": 0, "id": "c1",
             "function": {"name": "suggest_settings", "arguments": '{"sugges'}}]}}]}
        yield {"choices": [{"delta": {"tool_calls": [
            {"index": 0, "function": {"arguments":
             'tions":[{"field":"leverage","value":2,"reason":"меньше риск"}]}'}}]}}]}
    else:
        for word in ["Поставил ", "плечо x2."]:
            yield {"choices": [{"delta": {"content": word}}]}

class FakeClient:
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False

aitunnel.stream_chat_completion = fake_stream
aitunnel.build_client = lambda: FakeClient()
service_mod.aitunnel.stream_chat_completion = fake_stream
service_mod.aitunnel.build_client = lambda: FakeClient()

async def main():
    req = AssistantChatRequest(
        messages=[{"role": "user", "content": "посоветуй настройки"}],
        form={"step": 2, "tradingPair": "BTC/USDT", "leverage": "10"},
    )
    async for ev in service_mod.AssistantService(user_id="u1").stream(req):
        print(json.dumps(ev, ensure_ascii=False))

asyncio.run(main())
```

Ожидаемый вывод:

```
{"type": "status", "stage": "thinking"}
{"type": "suggestions", "items": [{"field": "leverage", "value": "2", ...}]}
{"type": "status", "stage": "thinking"}
{"type": "delta", "text": "Поставил "}
{"type": "delta", "text": "плечо x2."}
{"type": "done"}
```

Так удобно проверять именно склейку tool calls по кускам — самое хрупкое место
цикла. Веб-поиск подменяется так же: `tools_mod.aitunnel.complete = fake_complete`.

> В консоли Windows русский текст может выглядеть как «кракозябра» — это кодировка
> терминала (cp866), а не данные. Перенаправьте вывод в файл, если мешает.

---

## Отладка: симптом → причина

| Симптом | Вероятная причина | Куда смотреть |
|---|---|---|
| Панели и вкладки нет вообще | `AITUNNEL_API_KEY` не задан или бэкенд не перезапущен | `GET /assistant/status` |
| «Ассистент недоступен» сразу после отправки | 400/401 от бэкенда: нет ключа или протух JWT | Вкладка Network, ответ на `POST /assistant/chat` |
| Ответ приходит целиком в конце, а не по буквам | Буферизация SSE прокси | `proxy_buffering off` в nginx; в dev — проверьте, что не открыт прод-URL |
| Помощник отвечает текстом, но карточек «Применить» нет | Модель не умеет tool calling, либо промпт не требует вызывать `suggest_settings` | `AI_ASSISTANT_MODEL`, `SYSTEM_PROMPT` |
| Карточка появляется, но нужного поля в ней нет | Значение не прошло валидацию | Лог `info` «Dropped invalid assistant suggestion» с именем поля |
| Нажал «Применить» — в форме ничего не изменилось | Связанное поле не обновлено (например, `filters` без `strategyPreset: 'custom'` затирается пресетом) | `applySuggestions.ts` |
| Предложение применилось «не туда» | Имя поля в `SUGGESTABLE_FIELDS` не совпадает с ключом `formData` | `tools.py` ↔ `page.tsx` |
| Помощник предлагает MACD, Binance Spot, усреднение | Из промпта выпал список «чего в продукте нет» | `prompt.py` |
| Ответ обрывается на середине | Упёрлись в `max_tokens` | `aitunnel.stream_chat_completion` |
| В логах «Assistant hit tool-round limit» | Модель зациклилась на инструментах | `MAX_TOOL_ROUNDS` в `service.py`, описания инструментов |
| Русский текст рвётся «кракозяброй» в браузере | Потерян `{ stream: true }` в `TextDecoder` | `assistantApi.ts` |
| Панель зависла в «Думаю» | Не пришло событие `done` — стрим оборвался | Логи бэкенда, `exception` в `service.py` |
