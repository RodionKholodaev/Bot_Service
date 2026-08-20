# Рецепты: как писать тесты в Bot_Service

Типовые задачи по шагам. Как всё устроено — в [README.md](README.md).

---

## Оглавление

- [Добавить юнит-тест сервиса](#добавить-юнит-тест-сервиса)
- [Добавить интеграционный тест ручки](#добавить-интеграционный-тест-ручки)
- [Подменить сеть (HTTP)](#подменить-сеть-http)
- [Подменить Docker](#подменить-docker)
- [Подменить репозиторий вместо БД](#подменить-репозиторий-вместо-бд)
- [Проверить, что тест вообще работает](#проверить-что-тест-вообще-работает)
- [Мутационная проверка набора](#мутационная-проверка-набора)
- [Проверить лог и critical-алерт](#проверить-лог-и-critical-алерт)
- [Проверить выброс доменного исключения](#проверить-выброс-доменного-исключения)
- [Что тестировать, а что нет](#что-тестировать-а-что-нет)
- [Отладка: симптом → причина](#отладка-симптом--причина)
- [Чек-лист перед коммитом](#чек-лист-перед-коммитом)

---

## Добавить юнит-тест сервиса

Самый частый случай. Пример: в `StatsService` появился метод, считающий средний
размер сделки.

**1.** Найдите файл `backend/tests/unit/test_<имя_сервиса>.py` или создайте новый.

**2.** Если файл новый — начните с docstring, который отвечает на два вопроса:
*что здесь тестируется* и *почему без БД/сети*.

```python
"""
Юнит-тесты для XxxService.

<Зачем эти тесты вообще нужны: где тут легко ошибиться и чем это грозит.>

Тесты идут без сети и без БД: <как именно подменены зависимости>.
"""
```

**3.** Заведите фабрики, если у моделей много обязательных полей:

```python
def make_trade(*, profit_usdt: float | None = 0.0, close_time=None) -> Trade:
    """Создаёт сделку в памяти (без записи в БД) с разумными дефолтами."""
    return Trade(
        id=1, bot_id="bot-1", user_id=1, freqtrade_trade_id=1,
        pair="BTC/USDT", direction="long", open_rate=100.0, amount=1.0, leverage=1.0,
        profit_usdt=profit_usdt, close_time=close_time,
    )
```

Аргументы — **keyword-only** (`*` в начале), чтобы на вызове было видно, что задаётся.

**4.** Напишите тест по схеме Arrange / Act / Assert:

```python
@pytest.mark.asyncio
async def test_avg_trade_size_ignores_open_trades():
    # Arrange: одна сделка ещё открыта — в среднее она попасть не должна
    trades = [make_trade(profit_usdt=10.0), make_trade(profit_usdt=None)]
    service = StatsService(bot_repo=None, trade_repo=FakeTradeRepo(trades))  # type: ignore

    # Act
    result = await service.avg_trade_size()

    # Assert: считаем только по закрытой — 10 / 1, а не 10 / 2
    assert result == 10.0
```

**5.** Прогоните файл и убедитесь, что он **падает**, если сломать проверяемую строку
в сервисе (см. [ниже](#проверить-что-тест-вообще-работает)).

---

## Добавить интеграционный тест ручки

Нужен, когда важен HTTP-контракт: код ответа, форма JSON, авторизация.

```python
import pytest

@pytest.mark.asyncio
async def test_create_bot_requires_auth(client):
    response = await client.post("/bots", json={"name": "test"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_bot_success(client):
    # регистрация даёт токен — отдельной фикстуры для этого нет,
    # авторизуемся через настоящую ручку
    register = await client.post("/auth/register", json={
        "username": "rodion", "email": "test@test.com", "password": "12345678",
    })
    token = register.json()["access_token"]

    response = await client.post(
        "/bots",
        json={...},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json()["name"] == "..."
```

Фикстура `client` подключается по имени в аргументах теста, `clear_database` работает
автоматически — база перед каждым тестом пустая.

Если нужно подготовить данные напрямую, минуя ручки, возьмите `db_session`:

```python
@pytest.mark.asyncio
async def test_something(client, db_session):
    db_session.add(User(username="x", email="x@x.ru", password_hash="..."))
    await db_session.commit()
    ...
```

**Не дублируйте здесь бизнес-логику** — расчёты проверяются юнитами. Интеграционный
тест отвечает на вопрос «собралось ли всё вместе».

---

## Подменить сеть (HTTP)

Никаких реальных запросов. Два способа, в зависимости от того, где живёт клиент.

### Клиент передан аргументом — подсуньте фейк

Так устроен `polling_worker`: `httpx.AsyncClient` приходит параметром, поэтому
достаточно передать свой объект с методом `get`:

```python
class FakeApiClient:
    """
    Fake вместо httpx.AsyncClient — не ходит в сеть. Отвечает по пути запроса;
    путь, которого нет в responses, считается недоступным — так же, как выглядит
    мёртвый бот: соединение просто не устанавливается.
    """

    def __init__(self, responses: dict[str, FakeResponse]):
        self.responses = responses

    async def get(self, url: str, **kwargs) -> FakeResponse:
        path = "/" + url.split("/", 3)[3]
        if path not in self.responses:
            raise httpx.ConnectError("connection refused")
        return self.responses[path]
```

Использование:

```python
client = FakeApiClient({
    PING: FakeResponse({"status": "pong"}),
    TRADES: FakeResponse({"trades": []}),
})
client_dead = FakeApiClient({})   # молчит на всё — бот недоступен
```

### Клиент создаётся внутри — подмените класс через monkeypatch

Так устроен `ExchangeRateService`:

```python
monkeypatch.setattr(
    "src.services.commission_service.ExchangeRateService",
    lambda: FakeExchangeRateService(rate=90.0),
)
```

Путь — **туда, куда импортировали** (`commission_service`), а не туда, где объявили.

Если параметр нужен разный в разных тестах, заверните в фикстуру-сборщик:

```python
@pytest.fixture
def set_usdt_rate(monkeypatch):
    def _set(rate: float | None) -> None:
        monkeypatch.setattr(
            "src.services.commission_service.ExchangeRateService",
            lambda: FakeExchangeRateService(rate),
        )
    return _set


async def test_something(set_usdt_rate):
    set_usdt_rate(90.0)     # или set_usdt_rate(None) для «курс недоступен»
```

---

## Подменить Docker

`docker_manager` — модуль с функциями, вызываемыми как `docker_manager.stop_container(...)`.
Подменяются атрибуты модуля:

```python
@pytest.fixture
def stopped_containers(monkeypatch):
    """Подменяет docker_manager — тесты не трогают реальный Docker."""
    stopped: list[str] = []
    monkeypatch.setattr(docker_manager, "get_container_status", lambda cid: "running")
    monkeypatch.setattr(docker_manager, "get_container_logs", lambda cid, tail=50: "...")
    monkeypatch.setattr(docker_manager, "stop_container", lambda cid: stopped.append(cid))
    return stopped
```

Фикстура возвращает список — так тест проверяет не только состояние, но и **действие**:

```python
assert stopped_containers == ["container-1"]   # контейнер остановили
assert stopped_containers == []                # не трогали
```

---

## Подменить репозиторий вместо БД

Сервисы получают репозиторий в конструктор — значит, БД можно не поднимать.

### Простой случай: репозиторий сам возвращает данные

```python
class FakeBotRepository:
    """Fake вместо BotRepository — из всего репозитория здесь нужен только владелец бота."""

    def __init__(self, user: User | None):
        self._user = user

    async def get_user(self, user_id):
        return self._user
```

Реализуйте **только те методы, которые зовёт тестируемый код**. Если код начнёт звать
новый метод, тест упадёт с понятным `AttributeError` — это фича, а не проблема.

### Репозиторий создаётся внутри функции

`_async_bot_trades` делает `BotRepository(db)` прямо в теле. Подменяем класс на фабрику:

```python
monkeypatch.setattr(polling_worker, "BotRepository", lambda db: FakeBotRepository(user))
monkeypatch.setattr(polling_worker, "TradeRepository", lambda db: FakeTradeRepository(known))
```

### Сложный случай: сервис сам выполняет запрос

`StatsService` получает у репозитория `select(...)`, дописывает `.order_by(...)` и
выполняет через `trade_repo.db.execute(...)`. Нужно подделать всю цепочку:

```python
class _FakeQuery:
    """Заглушка вместо SQLAlchemy select(...). Возвращает себя и записывает вызовы."""
    def __init__(self):
        self.where_calls, self.order_by_calls = [], []
    def where(self, *args, **kwargs):
        self.where_calls.append(args); return self
    def order_by(self, *args, **kwargs):
        self.order_by_calls.append(args); return self


class _FakeScalars:
    def __init__(self, items): self._items = items
    def all(self): return self._items


class _FakeResult:
    def __init__(self, items): self._items = items
    def scalars(self): return _FakeScalars(self._items)


class FakeTradeRepo:
    def __init__(self, trades):
        self._trades = trades
        self.query = _FakeQuery()
        self.db = self                      # сервис зовёт trade_repo.db.execute(...)
    async def get_bot_close_trades(self, user_id, bot_id):
        return self.query
    async def execute(self, query):
        return _FakeResult(self._trades)
```

Такой фейк **слеп к содержимому запроса** — он отдаёт список независимо от фильтров.
Поэтому `_FakeQuery` записывает вызовы, и форма запроса проверяется отдельно:

```python
assert [str(a) for args in repo.query.order_by_calls for a in args] == ["trades.close_time ASC"]
```

Объекты SQLAlchemy напрямую не сравниваются (`==` строит выражение, а не даёт `bool`),
поэтому сравнивается их текст.

### Готовый фейк пользователей

`tests/fakes/test_user_repository.py` — `FakeUserRepository`, словарь в памяти с
автоинкрементом id. Берите его для всего, что связано с `AuthService`:

```python
from tests.fakes.test_user_repository import FakeUserRepository

repo = FakeUserRepository()
service = AuthService(repo)  # type: ignore
```

---

## Проверить, что тест вообще работает

**Тест, который никогда не падал, ничего не доказывает.** Прежде чем считать его
готовым, убедитесь, что он краснеет.

Быстрый способ — временно сломайте проверяемую строку в сервисе:

```python
# было
wins = [t for t in closed_trades if (t.profit_usdt or 0) > 0]
# стало (временно)
wins = [t for t in closed_trades if (t.profit_usdt or 0) >= 0]
```

Прогоните тест. Если он **прошёл** — он не проверяет то, что вы думаете. Верните код.

Типичные причины «зелёного при сломанном коде»:

- assert смотрит на значение, которое тест сам же задал в Arrange, а код его не трогает;
- фейк отдаёт результат в обход проверяемой логики;
- проверяемая ветка вообще не выполняется на этих данных.

Реальный пример из этого проекта: тест «неизвестное поле отбрасывается» проходил и
без белого списка полей — потому что такое поле отсеивалось следующей проверкой.
Тест был зелёным, но проверял не то, что заявлял.

---

## Мутационная проверка набора

То же самое, но по всему набору сразу и автоматически: скрипт по очереди вносит в
исходники по одной правке и смотрит, покраснели ли тесты. Правка, которую никто не
заметил, — это дыра в покрытии.

Скрипт одноразовый, в репозитории не хранится — соберите во временной папке:

```python
import subprocess, sys, pathlib

BACKEND = pathlib.Path(r"c:\програмирование\projects\Bot_Service\backend")

MUTANTS = [
    # (имя, файл, что заменить, на что)
    ("comm-profit-ge", "src/services/commission_service.py",
     "if profit > 0 and not trade.commission_paid:",
     "if profit >= 0 and not trade.commission_paid:"),
    ("poll-misses-gt", "src/services/polling_worker.py",
     "if misses >= MAX_PING_MISSES:", "if misses > MAX_PING_MISSES:"),
]

for mid, relpath, old, new in MUTANTS:
    path = BACKEND / relpath
    original = path.read_text(encoding="utf-8")
    if old not in original:
        print(f"SKIP {mid}: паттерн не найден"); continue
    try:
        path.write_text(original.replace(old, new, 1), encoding="utf-8")
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=no",
                            "-p", "no:cacheprovider"],
                           cwd=BACKEND, capture_output=True, text=True)
        print(f"{'ПОЙМАН' if r.returncode else 'ВЫЖИЛ'} {mid}")
    finally:
        path.write_text(original, encoding="utf-8")   # откат в любом случае
```

`try/finally` обязателен: без него упавший прогон оставит исходники сломанными.
После работы скрипта проверьте `git status` — дерево должно быть чистым.

Хорошие мутации — те, что имитируют реальную ошибку: сдвиг границы (`>` ↔ `>=`),
разворот сортировки, снятие проверки, замена операнда. На последнем прогоне набор
ловил все 23 мутанта.

Не каждый выживший мутант — дыра. Бывают **эквивалентные**: правка не меняет
поведение (например, `dd < max_dd` → `dd <= max_dd` при поиске минимума). Такие
пропускайте осознанно.

---

## Проверить лог и critical-алерт

`logger.critical(...)` — это не просто лог: `telegram_alerts.py` шлёт такие записи
разработчику в Telegram, а Sentry заводит событие. Поведение стоит проверять.

```python
@pytest.mark.asyncio
async def test_failure_alert_carries_last_ping_error(stopped_containers, caplog):
    ...
    with caplog.at_level(logging.CRITICAL, logger="src.services.polling_worker"):
        for _ in range(MAX_PING_MISSES):
            await _check_and_sync_bot(db, bot, client, ping_misses)  # type: ignore

    alerts = [r for r in caplog.records if r.levelno == logging.CRITICAL]
    assert len(alerts) == 1
    assert "ConnectError" in alerts[0].detail
```

Поля из `extra={...}` доступны как атрибуты записи: `extra={"detail": ...}` →
`alerts[0].detail`.

Обратная проверка не менее важна: сырой текст ошибки **не должен** попадать в
`Bot.error_message`, который видит пользователь.

```python
assert "ConnectError" not in bot.error_message
```

Проверяйте и **количество** алертов (`len(alerts) == 1`) — дребезг из воркера,
который крутится каждые 30 секунд, зальёт Telegram.

---

## Проверить выброс доменного исключения

```python
with pytest.raises(ConflictError):
    await service.register(body)
```

Если важен текст (он уезжает пользователю в HTTP `detail` и написан по-русски):

```python
with pytest.raises(UnauthorizedError) as exc_info:
    await service.login(body)

assert str(exc_info.value) == "Неверный email или пароль"
```

Не забудьте проверить, что состояние **не изменилось** — частая забытая половина:

```python
with pytest.raises(ValueError):
    await CommissionService.process_commission(trade, user, bot)

assert user.service_balance == 5000.0    # деньги не списаны
assert trade.commission_paid is False
```

---

## Что тестировать, а что нет

**Стоит:**

- расчёты, которые долго и легко ошибиться проверить руками (P&L, просадка, комиссия);
- границы и «неочевидные» правила продукта (ноль — это убыток; `paused` — это норма);
- всё, что трогает `User.service_balance`;
- защиту от повторов и дублей (`commission_paid`, `freqtrade_trade_id`);
- обработку недоверенного ввода (ответы модели, данные от freqtrade);
- поведение при отказе внешнего мира: бот молчит, курс недоступен, пользователя нет;
- условия, до которых в реальности ждать долго (`MAX_PING_MISSES` — это 90 секунд).

**Не стоит:**

- геттеры, `__init__` и прочий код без ветвлений;
- сам SQLAlchemy, FastAPI, pydantic — это чужие библиотеки, они протестированы;
- поведение freqtrade — проверяется только в dry-run руками;
- точные тексты логов (кроме упомянутого выше `critical`) — они меняются часто и
  ломали бы тесты без пользы.

**Правило:** если тест не может упасть по осмысленной причине, он только замедляет
набор и создаёт ложное чувство защищённости.

---

## Отладка: симптом → причина

| Симптом | Причина и что делать |
|---|---|
| `ModuleNotFoundError: No module named 'src'` | Запускаете не из `backend/`. `pythonpath = .` в `pytest.ini` считается от папки запуска |
| Тест зелёный, хотя код сломан | Проверьте [раздел выше](#проверить-что-тест-вообще-работает): скорее всего, assert смотрит на данные из Arrange или фейк обходит логику |
| `AttributeError` на фейке | Продакшн-код начал звать метод, которого у фейка нет. Допишите метод — заодно узнали, что зависимость выросла |
| Тесты проходят по одному, но падают вместе | Общее состояние. Проверьте, что данные готовятся в тесте, а не на уровне модуля, и что `clear_database` не отключена |
| Событие улетело в реальный Glitchtip | В `conftest.py` `sentry_sdk.init(dsn="")` должен идти **до** импорта `src.main` |
| Ошибка внешнего ключа при очистке БД | Таблицы удаляются в порядке `reversed(Base.metadata.sorted_tables)`. Новая модель должна быть импортирована, иначе её нет в метаданных |
| `assert None is False` на поле модели | `default=...` у колонки применяется только настоящим INSERT'ом. Пишите `assert not obj.field` |
| Пустой список сделок вместо ожидаемых | В `FakeApiClient` путь не совпал с ключом в `responses` — сверьте константы `PING` / `TRADES` / `SHOW_CONFIG` |
| Изменения в `monkeypatch` протекли в другой тест | `monkeypatch` откатывается сам. Если протекло — значит, патчили через `setattr` руками или меняли глобальный объект |

---

## Чек-лист перед коммитом

- [ ] `python -m pytest` из `backend/` — весь набор зелёный
- [ ] Новый тест **проверенно падает**, если сломать проверяемую строку
- [ ] Имя теста читается как утверждение о поведении
- [ ] Есть `# Arrange` / `# Act` / `# Assert`
- [ ] Рядом с неочевидным `assert` — комментарий «почему именно столько»
- [ ] Ни одного реального похода в сеть, Docker или боевую БД
- [ ] `git status` чист — не остался сломанный исходник после экспериментов
- [ ] Если добавили модель — она импортируется, иначе не попадёт в `create_all` и в очистку
- [ ] Правили бэкенд — `ruff check .` и `ruff format --check .` из `backend/` зелёные
      (см. [Линт, форматирование и security-проверки](README.md#линт-форматирование-и-security-проверки))
- [ ] Правили фронтенд — `npm run format:check` из `frontend/` зелёный; `npm run lint`
      не обязан быть зелёным целиком (см. там же), но не добавляйте новых ошибок своим кодом
