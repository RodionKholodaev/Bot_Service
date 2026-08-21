# Фронтенд ИИ-помощника

Разбор `frontend/app/bot-creation/assistant/` и правок в `page.tsx`.

Общая картина — в [README.md](README.md). Бэкенд — в [backend.md](backend.md).

---

## Оглавление

- [Дерево компонентов](#дерево-компонентов)
- [Поток данных](#поток-данных)
- [Интеграция в page.tsx](#интеграция-в-pagetsx)
- [types.ts](#typests)
- [assistantApi.ts — транспорт и разбор SSE](#assistantapits--транспорт-и-разбор-sse)
- [useAssistantChat](#useassistantchat)
- [Компоненты](#компоненты)
- [applySuggestions.ts и fieldMeta.ts](#applysuggestionsts-и-fieldmetats)
- [Вёрстка и layout](#вёрстка-и-layout)
- [Мелочи UX, которые легко сломать](#мелочи-ux-которые-легко-сломать)

---

## Дерево компонентов

```
page.tsx  (CreateBotPage)
│
├── AssistantLauncher          вкладка у правого края + разовая подсказка
│
└── AssistantPanel             панель целиком, всегда смонтирована
    │   └── useAssistantChat   ← вся логика диалога живёт здесь
    │
    ├── .ai-backdrop           затемнение (только на узких экранах)
    ├── header                 иконка, заголовок, «начать заново», «закрыть»
    ├── .ai-panel__scroll
    │   ├── WelcomeState       пустое состояние + быстрые вопросы
    │   └── .ai-thread
    │       ├── MessageBubble[]
    │       │   ├── Markdown           текст ответа
    │       │   ├── SuggestionCard     предложения настроек
    │       │   └── ссылки-источники
    │       └── PhaseIndicator  «Думаю» / «Ищу в интернете»
    └── Composer               ввод, стоп, тумблер веб-поиска
```

Разделение простое: **`useAssistantChat` знает всё про диалог, компоненты не знают
ничего** — они получают готовое состояние и колбэки. Поэтому любой компонент можно
переписать, не трогая логику, и наоборот.

---

## Поток данных

```
1. Пользователь пишет вопрос (или жмёт быстрый промпт)
        │
2. useAssistantChat.send()
        │  getSnapshot() ── читает formData прямо сейчас, а не при рендере
        ▼
3. streamAssistantChat() → POST /api/assistant/chat
        │
4. события SSE ──► switch в send():
        │           status      → phase / searchQuery
        │           delta       → накопление текста, patchMessage
        │           suggestions → в сообщение
        │           sources     → в сообщение
        │           error       → в сообщение
        ▼
5. Пользователь жмёт «Применить» в SuggestionCard
        │
6. onApplySuggestions() → page.tsx → applySuggestionsToForm() → setFormData()
        │
7. setCurrentStep(firstStepOf(...)) — перескок на шаг, где поле видно
```

---

## Интеграция в `page.tsx`

Всё, что добавилось на странице (~55 строк):

```tsx
// 1. Показывать ли помощника вообще
const [assistantEnabled, setAssistantEnabled] = useState(false);
const [assistantOpen, setAssistantOpen] = useState(false);

useEffect(() => {
  if (!isAuthed) return;
  fetchAssistantStatus()
    .then(status => setAssistantEnabled(status.enabled))
    .catch(() => setAssistantEnabled(false));
}, [isAuthed]);

// 2. Снимок формы — читается в момент отправки вопроса
const getAssistantSnapshot = useCallback(
  () => toSnapshot(formData, currentStep, apiKeys.length > 0),
  [formData, currentStep, apiKeys.length],
);

// 3. Применение предложений
const handleApplySuggestions = useCallback((suggestions: Suggestion[]) => {
  setFormData(prev => applySuggestionsToForm(prev, suggestions, apiKeys[0]));
  setSubmitError(null);
  setCurrentStep(firstStepOf(suggestions));
}, [apiKeys]);
```

Плюс класс на корневом `div` и рендер в конце:

```tsx
<div className={`create-bot-page ${assistantEnabled && assistantOpen ? 'assistant-open' : ''}`}>
  ...
  {assistantEnabled && (
    <>
      <AssistantLauncher open={assistantOpen} onOpen={() => setAssistantOpen(true)} />
      <AssistantPanel
        open={assistantOpen}
        onClose={() => setAssistantOpen(false)}
        step={currentStep}
        getSnapshot={getAssistantSnapshot}
        onApplySuggestions={handleApplySuggestions}
      />
    </>
  )}
</div>
```

Ещё одна правка: тип `formData` переехал в `applySuggestions.ts` как
`BotFormValues`, и `useState<BotFormValues>({...})` теперь типизирован явно.
Раньше тип выводился из литерала — этого хватало форме, но не хватало помощнику,
которому нужно ссылаться на ту же структуру.

---

## `types.ts`

Общий словарь с бэкендом. Ключевые типы:

```ts
type SuggestableField = 'dryRun' | 'stakeAmount' | ... ;   // синхронно с SUGGESTABLE_FIELDS
interface Suggestion { field: SuggestableField; value: ...; reason: string }
type AssistantPhase = 'idle' | 'thinking' | 'searching' | 'streaming';
type AssistantEvent = { type: 'status'; ... } | { type: 'delta'; ... } | ... ;
interface BotFormSnapshot { step, dryRun, stakeAmount, ... }
```

`AssistantEvent` — размеченное объединение, поэтому `switch (event.type)` в хуке
проверяется компилятором: добавите событие на бэкенде, забудете здесь — TypeScript
не скажет ничего (события приходят по сети), **но** забудете ветку в `switch` при
добавленном типе — скажет. Поэтому правило: новое событие сначала в `types.ts`,
потом в хук.

---

## `assistantApi.ts` — транспорт и разбор SSE

### Почему не `lib/api.ts`

Общий `apiFetch` читает тело целиком (`await res.text()`) — для стрима не годится.
`EventSource` тоже не подходит: он умеет только GET и не даёт поставить заголовок
`Authorization`. Поэтому здесь обычный `fetch` + ручное чтение `ReadableStream`.

Токен берётся из `localStorage` так же, как в `lib/api.ts` — единая схема авторизации.

### Разбор потока

```ts
async function* readSseLines(body: ReadableStream<Uint8Array>): AsyncGenerator<string>
```

Копит куски в буфер, режет по `\n\n` (граница SSE-события), из каждого события
достаёт строки, начинающиеся с `data:`. Важно, что чанк сети **не равен** событию:
одно событие может приехать двумя чанками, а два события — одним. Отсюда буфер
и цикл `while (boundary !== -1)`.

`decoder.decode(value, { stream: true })` обязателен: без флага `stream`
многобайтовый символ UTF-8, разрезанный на границе чанков, превратится в «кракозябру» —
а у нас весь текст русский.

### Ошибки

Если ответ не 200 или без тела, генератор сам отдаёт `error` + `done` — вызывающий
код не различает «упало на HTTP» и «упало внутри стрима», обрабатывает одинаково.

Два нюанса в разборе тела ошибки:

- **`detail` берётся, только если это строка.** У доменных исключений проекта
  `detail` — строка, а у 422 от FastAPI это массив объектов, который `String()`
  показал бы пользователю как «[object Object]».
- **`kind` проставляет фронт, а не бэкенд.** `429` помечается как `'rate_limit'`
  (см. [backend.md](backend.md#rate-limit)), всё остальное — `'generic'`.
  `MessageBubble` рисует лимит янтарной плашкой с часами вместо красной с
  восклицательным знаком: упереться в лимит — норма, а не сбой. В событиях
  самого SSE-потока поля `kind` нет.

Отдельно: сообщения с пустым `content` **не** попадают в историю следующего
запроса. Оборвавшийся ответ остаётся пузырём с `content: ''`, а `ChatMessage`
на бэкенде требует `min_length=1` — без фильтрации весь следующий запрос падал бы
на валидации, и диалог был бы сломан до кнопки «Начать заново».

---

## `useAssistantChat`

Единственное место, где живёт состояние диалога.

```ts
const {
  messages,      // AssistantMessage[]
  phase,         // 'idle' | 'thinking' | 'searching' | 'streaming'
  searchQuery,   // что именно ищем (для индикатора)
  webSearch, setWebSearch,
  isBusy,        // phase !== 'idle'
  send, stop, reset,
} = useAssistantChat({ getSnapshot });
```

### Как устроен `send`

1. Складывает вопрос пользователя и **пустой** пузырь ассистента в `messages` —
   так лента сразу реагирует на отправку.
2. Ставит `phase = 'thinking'`.
3. Идёт по событиям и раскладывает их (см. таблицу в [README.md](README.md#события-sse)).
4. В `finally` возвращает `phase = 'idle'` и — важная деталь — если пузырь так и
   остался пустым (ни текста, ни предложений, ни ошибки), подставляет туда ошибку.
   Иначе в ленте висел бы «призрак»: пустой ответ без объяснений.

### Почему текст копится в локальной переменной

```ts
let buffer = '';
...
case 'delta':
  buffer += event.text;
  patchMessage(replyId, { content: buffer });
```

Токены приходят десятками в секунду. Читать предыдущее значение из состояния на
каждый токен — лишний повод для рассинхрона; копим в замыкании и пишем готовую
строку.

### Отмена

`AbortController` в `abortRef`. Он же — флаг занятости: пока `abortRef.current`
не пуст, повторный `send` игнорируется. `AbortError` в `catch` не считается
ошибкой — пользователь сам нажал «Стоп». Плюс `useEffect` с пустыми зависимостями
обрывает запрос при уходе со страницы.

### Ref истории

```ts
const messagesRef = useRef<AssistantMessage[]>([]);
useEffect(() => { messagesRef.current = messages; }, [messages]);
```

Нужен, чтобы `send` собирал историю без попадания `messages` в зависимости
(иначе колбэк пересоздаётся на каждый токен). Присваивание вынесено в эффект
намеренно — запись в ref во время рендера ловит правило `react-hooks/refs`
в новом eslint-конфиге Next 16. `send` вызывается только из обработчиков событий,
то есть всегда после коммита, так что ref к этому моменту актуален.

---

## Компоненты

### `AssistantLauncher`

Вкладка у правого края, ~40px в ширину, подпись `writing-mode: vertical-rl`.
При открытой панели уезжает (`.is-hidden`), панель закрывается своим крестиком.

Разовая подсказка: через 0.9 с после монтирования всплывает пузырь «Не знаете,
что выбрать?», через 9 с сам исчезает. Флаг `assistant_hint_seen` в `localStorage`
ставится **при явном действии** — закрытии крестиком или открытии панели.
То есть если пользователь подсказку не заметил, в следующий раз она покажется
снова; если заметил и отреагировал — больше не побеспокоит.

### `AssistantPanel`

Оболочка. Три вещи, которые стоит знать:

- **Всегда смонтирована**, закрытие — это `transform: translateX(100%)`. Поэтому
  диалог не теряется при сворачивании. Обратная сторона: `useAssistantChat`
  работает и при закрытой панели, но без активного запроса он ничего не делает.
- **Автоскролл** — `scrollTop = scrollHeight` в эффекте на `[messages, phase, open]`.
- **Esc** закрывает панель; слушатель вешается только когда `open`.

### `MessageBubble`

Пузырь пользователя — простой текст с `white-space: pre-wrap`.
Пузырь ассистента — аватар + тело, внутри по порядку: `Markdown`, курсор (если
это последнее сообщение и идёт стриминг), `SuggestionCard`, ссылки, плашка ошибки.
Любой из блоков может отсутствовать.

### `SuggestionCard`

Карточка предложений. Локальное состояние `applied: Set<field>` — только для вида
кнопок; настоящее применение уходит наверх через `onApply`. Кнопка «Применить всё»
появляется, когда предложений больше одного. Для `filters` дополнительно рисуются
чипы правил (`RSI 5m < 30`) в цветах индикатора.

### `WelcomeState`

Пустое состояние. Быстрые вопросы зависят от текущего шага мастера
(`PROMPTS_BY_STEP`) — на шаге «Пара и плечо» спрашивать про Take Profit бессмысленно.
Правится в одном месте, это обычный словарь.

### `PhaseIndicator`

«Думаю» или «Ищу в интернете «запрос»» с тремя прыгающими точками. При
`phase === 'streaming'` **ничего не показывает** — там уже бежит сам текст,
два индикатора одновременно выглядели бы как зависание.

### `Composer`

Textarea, растущая до 120px. Enter отправляет, Shift+Enter — перенос строки.
Во время ответа кнопка отправки заменяется на «Стоп». Ниже — тумблер веб-поиска
(состояние живёт в хуке, потому что уезжает в тело запроса).

### `Markdown`

Минимальный рендерер: абзацы, маркированные и нумерованные списки, `**жирный**`,
`` `код` ``. Заголовки `#` превращаются в обычный текст.

Сделан **React-узлами, без `dangerouslySetInnerHTML`** — ответ модели это
недоверенный текст, и полноценная markdown-библиотека с поддержкой HTML была бы
дырой. Заодно нет лишней зависимости.

Если понадобится больше синтаксиса — правится `INLINE` (регулярка инлайн-разметки)
и `toBlocks` (разбор построчно).

---

## `applySuggestions.ts` и `fieldMeta.ts`

### `applySuggestionsToForm(form, suggestions, firstApiKey?)`

Чистая функция: форма + предложения → новая форма. Кроме самого значения тянет
за собой связанные поля, иначе форма окажется в противоречивом состоянии:

| Поле | Что ещё меняется | Почему |
|---|---|---|
| `filters` | `strategyPreset = 'custom'` | Иначе `useEffect` в `page.tsx` тут же перезапишет фильтры значениями пресета |
| `stopLoss` | `useStopLoss = true` | Без галочки значение не уедет на бэкенд |
| `dryRun: false` | подставляется первый API-ключ и его биржа | Боевой режим без ключа не пройдёт валидацию формы |
| `dryRun: true` | ключ очищается, `exchange = 'binance'` | Повторяет логику `handleDryRunToggle` |

**Это первое место, куда стоит смотреть**, если предложение применяется, а в форме
ничего не меняется или меняется не то.

### `toSnapshot(form, step, hasApiKeys)`

Обратное преобразование: из формы в снимок для помощника. Отбрасывает то, что ему
знать не нужно (`selectedApiKeyId`, `trailingStop`).

### `fieldMeta.ts`

Как показать предложение человеку: подпись, номер шага мастера и формат значения.

```ts
leverage: { label: 'Плечо', step: 2, format: (v) => `x${v}` }
```

`step` используется в `firstStepOf()` — после применения страница перескакивает на
минимальный из затронутых шагов, чтобы изменение было видно.

---

## Вёрстка и layout

`assistant.css`. Все классы с префиксом `ai-`, плюс один класс на странице —
`.create-bot-page.assistant-open`. Файл `create-bot.css` **не тронут**.

### Две раскладки

```css
/* ≥1180px: страница ужимается, форма видна целиком */
@media (min-width: 1180px) {
  .create-bot-page.assistant-open {
    padding-right: calc(var(--ai-width) + 24px);
  }
}

/* <1180px: панель поверх + затемнение */
@media (max-width: 1179px) {
  .ai-backdrop.is-open { display: block; ... }
}
```

Работает это потому, что `.create-bot-container` внутри — `max-width: 900px;
margin: 0 auto`. Когда у страницы появляется правый отступ, форма просто
перецентровывается в оставшемся пространстве. Никаких `position`/`grid`-переделок
существующей вёрстки не потребовалось.

`--ai-width` объявлена в `:root`, потому что нужна и панели, и правилу сдвига
страницы — это разные элементы, из панели переменная бы не «дотянулась».

### Токены

Остальные переменные (`--ai-bg`, `--ai-accent`, `--ai-line`, `--ai-text`,
`--ai-muted`, `--ai-dim`) объявлены на `.ai-panel, .ai-launcher`. Значения взяты
из `create-bot.css` — та же палитра `#0f1729 / #60a5fa / #e4e7f0 / #9ca3af`,
те же радиусы и та же кривая анимации, поэтому панель читается как часть страницы,
а не как виджет поверх чужого дизайна.

### Анимации

Все с префиксом `ai-`: `ai-fade`, `ai-msg-in`, `ai-hint-in`, `ai-blink` (курсор),
`ai-bounce` (точки), `ai-spin` (глобус поиска). В конце файла — блок
`@media (prefers-reduced-motion: reduce)`, отключающий движение.

---

## Мелочи UX, которые легко сломать

Если будете переписывать компоненты — вот что стоит сохранить:

| Что | Зачем |
|---|---|
| Панель не размонтируется при закрытии | Иначе теряется история диалога |
| `PhaseIndicator` молчит во время `streaming` | Два индикатора сразу читаются как зависание |
| Пустой ответ превращается в ошибку | Иначе в ленте висит пузырь-призрак |
| Автоскролл на `[messages, phase, open]` | Без `open` лента при открытии показывает верх переписки |
| `firstStepOf` после применения | Пользователь должен увидеть, что изменилось |
| Флаг подсказки ставится по действию, а не по показу | Иначе единственный шанс её заметить сгорает молча |
| Enter отправляет, Shift+Enter переносит | Ожидаемое поведение чата |
| `stream: true` в декодере SSE | Иначе русский текст рвётся на границах чанков |
