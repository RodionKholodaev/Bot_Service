"""
Юнит-тесты для polling_worker — фонового цикла, который следит за живостью ботов
и тянет из них сделки.

Две группы тестов:

1. Здоровье бота (_ping_bot, _check_and_sync_bot). Правило «мёртв после
   MAX_PING_MISSES промахов подряд» руками не проверишь: чтобы увидеть его в бою,
   нужно уронить контейнер и ждать полторы минуты. Здесь оно проверяется за
   миллисекунды — счётчик промахов передаётся в функцию явным аргументом.

2. Синхронизация сделок (_async_bot_trades). Здесь живут деньги: именно отсюда
   вызывается начисление комиссии, а дедупликация по freqtrade_trade_id — то, что
   не даёт записать одну сделку дважды.

Ни сети, ни Docker, ни БД: httpx-клиент, docker_manager, репозитории и сервис
курса подменяются фейками.
"""

import logging

import httpx
import pytest

from src.models.bot import Bot
from src.models.trade import Trade
from src.models.user import User
from src.services import docker_manager, polling_worker
from src.services.commission_service import CommissionService
from src.services.polling_worker import (
    MAX_PING_MISSES,
    _async_bot_trades,
    _check_and_sync_bot,
    _ping_bot,
)

PING = "/api/v1/ping"
SHOW_CONFIG = "/api/v1/show_config"
TRADES = "/api/v1/trades"


class FakeResponse:
    def __init__(self, payload: dict | None = None, status_code: int = 200):
        self._payload = payload or {}
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)  # type: ignore

    def json(self):
        return self._payload


class FakeApiClient:
    """
    Fake вместо httpx.AsyncClient — не ходит в сеть. Отвечает по пути запроса;
    путь, которого нет в responses, считается недоступным — так же, как выглядит
    мёртвый бот: соединение просто не устанавливается.
    """

    def __init__(self, responses: dict[str, FakeResponse]):
        self.responses = responses
        self.requested_paths: list[str] = []

    async def get(self, url: str, **kwargs) -> FakeResponse:
        path = "/" + url.split("/", 3)[3]
        self.requested_paths.append(path)
        if path not in self.responses:
            raise httpx.ConnectError("connection refused")
        return self.responses[path]


class FakeSession:
    """Fake вместо AsyncSession — запоминает добавленные объекты и считает коммиты."""

    def __init__(self):
        self.commits = 0
        self.added: list = []

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def flush(self):
        pass

    async def refresh(self, obj):
        pass


def make_bot(**overrides) -> Bot:
    defaults = {
        "id": "bot-1",
        "user_id": 1,
        "status": "running",
        "container_id": "container-1",
        "api_port": 9000,
        "api_username": "user",
        "api_password": "pass",
        "leverage": 5,
        "total_profit": 0.0,
        "total_commission_paid_usdt": 0.0,
        "total_commission_paid_rub": 0.0,
    }
    defaults.update(overrides)
    return Bot(**defaults)


@pytest.fixture
def stopped_containers(monkeypatch):
    """Подменяет docker_manager — тесты не трогают реальный Docker."""
    stopped: list[str] = []
    monkeypatch.setattr(docker_manager, "get_container_status", lambda cid: "running")
    monkeypatch.setattr(docker_manager, "get_container_logs", lambda cid, tail=50: "Could not load markets")
    monkeypatch.setattr(docker_manager, "stop_container", lambda cid: stopped.append(cid))
    return stopped


# ── ping ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ping_returns_none_when_bot_answers():
    # Arrange
    bot = make_bot()
    client = FakeApiClient({PING: FakeResponse({"status": "pong"})})

    # Act
    ping_error = await _ping_bot(bot, client)  # type: ignore

    # Assert
    assert ping_error is None


@pytest.mark.asyncio
async def test_ping_returns_error_text_when_bot_is_unreachable():
    # Arrange
    bot = make_bot()
    client = FakeApiClient({})  # ни один путь не отвечает

    # Act
    ping_error = await _ping_bot(bot, client)  # type: ignore

    # Assert
    # Тип обязателен: у httpx-исключений сообщение часто пустое, и без него
    # в алерте не видно, что произошло.
    assert ping_error is not None
    assert "ConnectError" in ping_error


# ── правило MAX_PING_MISSES ───────────────────────────────────


@pytest.mark.asyncio
async def test_bot_is_not_failed_before_max_misses(stopped_containers):
    # Arrange
    # Одного промаха мало: столько же длится перезапуск контейнера и медленный
    # старт freqtrade — иначе здоровые боты уходили бы в error.
    bot = make_bot()
    db = FakeSession()
    client = FakeApiClient({})
    ping_misses: dict[str, int] = {}

    # Act
    for _ in range(MAX_PING_MISSES - 1):
        await _check_and_sync_bot(db, bot, client, ping_misses)  # type: ignore

    # Assert
    assert bot.status == "running"
    assert ping_misses[bot.id] == MAX_PING_MISSES - 1
    assert stopped_containers == []


@pytest.mark.asyncio
async def test_bot_is_failed_and_stopped_after_max_misses(stopped_containers):
    # Arrange
    bot = make_bot()
    db = FakeSession()
    client = FakeApiClient({})
    ping_misses: dict[str, int] = {}

    # Act
    for _ in range(MAX_PING_MISSES):
        await _check_and_sync_bot(db, bot, client, ping_misses)  # type: ignore

    # Assert
    assert bot.status == "error"
    assert bot.error_message is not None
    assert "not responding" in bot.error_message
    # контейнер останавливаем как реакцию: он держит порт и память, а при отказе
    # на старте процесс freqtrade зависает в shutdown и сам не умрёт
    assert stopped_containers == ["container-1"]
    assert db.commits == 1
    # счётчик снят — бот больше не в работе, повторный алерт не уйдёт
    assert bot.id not in ping_misses


@pytest.mark.asyncio
async def test_failure_alert_carries_last_ping_error(stopped_containers, caplog):
    # Arrange
    # Сама причина промахов живёт только в памяти воркера. Если не донести её до
    # алерта, разработчик получит "не отвечает 90 секунд" и не узнает, что это было:
    # отказ соединения, таймаут или 502 от freqtrade.
    bot = make_bot()
    db = FakeSession()
    client = FakeApiClient({})
    ping_misses: dict[str, int] = {}

    # Act
    with caplog.at_level(logging.CRITICAL, logger="src.services.polling_worker"):
        for _ in range(MAX_PING_MISSES):
            await _check_and_sync_bot(db, bot, client, ping_misses)  # type: ignore

    # Assert
    alerts = [record for record in caplog.records if record.levelno == logging.CRITICAL]
    assert len(alerts) == 1
    assert "ConnectError" in alerts[0].detail
    # а в error_message, который видит пользователь, сырой текст ошибки не попадает
    assert bot.error_message is not None
    assert "ConnectError" not in bot.error_message


@pytest.mark.asyncio
async def test_miss_counter_resets_when_bot_answers_again(stopped_containers):
    # Arrange
    bot = make_bot()
    db = FakeSession()
    ping_misses: dict[str, int] = {}
    dead_client = FakeApiClient({})
    alive_client = FakeApiClient(
        {
            PING: FakeResponse({"status": "pong"}),
            TRADES: FakeResponse({"trades": []}),
            SHOW_CONFIG: FakeResponse({"state": "running"}),
        }
    )

    # Act
    await _check_and_sync_bot(db, bot, dead_client, ping_misses)  # type: ignore
    await _check_and_sync_bot(db, bot, alive_client, ping_misses)  # type: ignore

    # Assert
    assert ping_misses == {}
    assert bot.status == "running"
    assert stopped_containers == []


# ── состояние торгового цикла ─────────────────────────────────


@pytest.mark.asyncio
async def test_bot_is_failed_when_freqtrade_stopped_trading(stopped_containers):
    # Arrange
    # Поймав OperationalException, freqtrade переводит себя в "stopped" и продолжает
    # крутиться пустым циклом: контейнер, порт и ping выглядят здоровыми, торговли нет.
    bot = make_bot()
    db = FakeSession()
    client = FakeApiClient(
        {
            PING: FakeResponse({"status": "pong"}),
            TRADES: FakeResponse({"trades": []}),
            SHOW_CONFIG: FakeResponse({"state": "stopped"}),
        }
    )

    # Act
    await _check_and_sync_bot(db, bot, client, {})  # type: ignore

    # Assert
    assert bot.status == "error"
    assert bot.error_message is not None
    assert "stopped" in bot.error_message
    assert stopped_containers == ["container-1"]


@pytest.mark.asyncio
async def test_paused_state_is_not_a_failure(stopped_containers):
    # Arrange
    # paused — штатное состояние freqtrade, обработка в нём продолжается.
    bot = make_bot()
    db = FakeSession()
    client = FakeApiClient(
        {
            PING: FakeResponse({"status": "pong"}),
            TRADES: FakeResponse({"trades": []}),
            SHOW_CONFIG: FakeResponse({"state": "paused"}),
        }
    )

    # Act
    await _check_and_sync_bot(db, bot, client, {})  # type: ignore

    # Assert
    assert bot.status == "running"
    assert stopped_containers == []


# ── синхронизация сделок (_async_bot_trades) ──────────────────


class FakeBotRepository:
    """Fake вместо BotRepository — из всего репозитория здесь нужен только владелец бота."""

    def __init__(self, user: User | None):
        self._user = user

    async def get_user(self, user_id):
        return self._user


class FakeTradeRepository:
    """Fake вместо TradeRepository — сделки, которые сервис уже знает.

    Ключ тот же, что и в бою: (bot_id, freqtrade_trade_id). Именно по нему код
    решает, создавать новую запись или обновлять существующую.
    """

    def __init__(self, known: tuple[Trade, ...] = ()):
        self._known = {(t.bot_id, t.freqtrade_trade_id): t for t in known}

    async def get_trade(self, bot_id, ft_id):
        return self._known.get((bot_id, ft_id))


class FakeExchangeRateService:
    """Fake вместо ExchangeRateService — не ходит в сеть за курсом USDT/RUB."""

    async def get_usdt_rub(self):
        return 90.0


class SpyCommissionService:
    """Обёртка над настоящим CommissionService: считает вызовы, но работу не подменяет.

    Нужна там, где решение «начислять или нет» принимает polling_worker, а не сам
    CommissionService. У открытой сделки profit_usdt=None, поэтому лишний вызов
    ничего бы не изменил — по состоянию объектов его не отличить от отсутствия
    вызова. Шпион делает это различие видимым.
    """

    def __init__(self):
        self.calls: list[Trade] = []

    async def process_commission(self, trade, user, bot):
        self.calls.append(trade)
        await CommissionService.process_commission(trade, user, bot)


def make_user(*, commission_rate: float = 0.1, service_balance: float = 5000.0) -> User:
    return User(id=1, commission_rate=commission_rate, service_balance=service_balance)


def make_known_trade(*, freqtrade_trade_id: int = 1, close_time=None) -> Trade:
    """Сделка, уже лежащая в нашей таблице. close_time=None — ещё открыта."""
    return Trade(
        id=1,
        bot_id="bot-1",
        user_id=1,
        freqtrade_trade_id=freqtrade_trade_id,
        pair="BTC/USDT",
        direction="long",
        open_rate=100.0,
        amount=1.0,
        leverage=5,
        commission_paid=False,
        close_time=close_time,
    )


def make_raw_trade(
    *,
    trade_id: int = 1,
    is_open: bool = False,
    profit_abs: float = 10.0,
    profit_ratio: float = 0.05,
    is_short: bool = False,
) -> dict:
    """Сделка в том виде, в каком её отдаёт /api/v1/trades у freqtrade."""
    return {
        "trade_id": trade_id,
        "is_open": is_open,
        "pair": "BTC/USDT",
        "is_short": is_short,
        "open_rate": 100.0,
        "close_rate": 110.0,
        "amount": 1.0,
        "profit_abs": profit_abs,
        "profit_ratio": profit_ratio,
        "exit_reason": "roi",
        "open_date": "2026-01-01T10:00:00+00:00",
        "close_date": "2026-01-01T12:00:00+00:00",
    }


@pytest.fixture
def sync_env(monkeypatch):
    """Подменяет всё, за что _async_bot_trades цепляется снаружи.

    Репозитории патчатся по именам внутри polling_worker: модуль импортировал классы
    к себе, поэтому подмена в модуле-источнике на уже импортированные имена не
    подействовала бы. Курс патчится в commission_service — там его берут.

    Возвращает функцию-сборщик, чтобы каждый тест задавал своего владельца и свой
    набор уже известных сделок. Сборщик отдаёт SpyCommissionService — через него
    можно проверить, начислялась ли комиссия вообще.
    """

    def _install(*, user: User | None, known: tuple[Trade, ...] = ()) -> SpyCommissionService:
        spy = SpyCommissionService()
        monkeypatch.setattr(polling_worker, "BotRepository", lambda db: FakeBotRepository(user))
        monkeypatch.setattr(polling_worker, "TradeRepository", lambda db: FakeTradeRepository(known))
        monkeypatch.setattr(polling_worker, "CommissionService", spy)
        monkeypatch.setattr(
            "src.services.commission_service.ExchangeRateService",
            lambda: FakeExchangeRateService(),
        )
        return spy

    return _install


@pytest.mark.asyncio
async def test_new_closed_trade_is_saved_and_commission_charged(sync_env):
    # Arrange: freqtrade отдал закрытую сделку, которой у нас ещё нет
    bot = make_bot()
    user = make_user()
    db = FakeSession()
    commission = sync_env(user=user)

    # Act
    await _async_bot_trades(db, bot, [make_raw_trade(profit_abs=10.0)])  # type: ignore

    # Assert: запись создана и заполнена результатом сделки
    assert len(db.added) == 1
    trade = db.added[0]
    assert trade.freqtrade_trade_id == 1
    assert trade.bot_id == "bot-1"
    assert trade.direction == "long"
    assert trade.profit_usdt == 10.0
    assert trade.profit_pct == 5.0  # profit_ratio 0.05 -> проценты
    assert trade.close_time is not None
    # плечо берётся у бота: freqtrade его в сделке не отдаёт
    assert trade.leverage == 5

    # Комиссия начислена сразу: сделка пришла уже закрытой
    assert commission.calls == [trade]
    assert trade.commission_paid is True
    assert user.service_balance == 4910.0  # 5000 - (10 * 0.1 * 90)
    assert bot.total_profit == 10.0
    assert db.commits == 1


@pytest.mark.asyncio
async def test_new_open_trade_is_saved_without_result_and_commission(sync_env):
    # Arrange
    # Открытая сделка — это ещё не результат. Плавающий профит freqtrade показывает,
    # но записывать его нельзя: комиссия берётся один раз при закрытии, и «прибыльная»
    # открытая позиция списала бы деньги за то, что может уйти в убыток.
    bot = make_bot()
    user = make_user()
    db = FakeSession()
    commission = sync_env(user=user)

    # Act
    await _async_bot_trades(db, bot, [make_raw_trade(is_open=True)])  # type: ignore

    # Assert
    assert len(db.added) == 1
    trade = db.added[0]
    assert trade.profit_usdt is None
    assert trade.profit_pct is None
    assert trade.close_rate is None
    assert trade.close_time is None
    assert trade.exit_reason is None
    # Комиссию даже не запускаем: решение принимает polling_worker по флагу is_open.
    # Без этой проверки правку `if not is_open` на `if True` не поймать — у открытой
    # сделки profit=None, и лишний вызов прошёл бы вхолостую, ничего не изменив.
    assert commission.calls == []
    # not ..., а не `is False`: default=False у колонки — это значение по умолчанию для
    # INSERT, и проставляет его настоящий flush(). У объекта, который ещё не долетел до
    # БД (а в тестах не долетит никогда), поле остаётся None. Проверяем смысл — «комиссия
    # не начислена», — а не конкретное представление флага.
    assert not trade.commission_paid
    assert user.service_balance == 5000.0
    assert bot.total_profit == 0.0


@pytest.mark.asyncio
async def test_known_trade_is_not_saved_twice(sync_env):
    # Arrange
    # Главная защита от дублей: freqtrade отдаёт последние 500 сделок на каждый опрос,
    # то есть одну и ту же закрытую сделку мы видим снова каждые 30 секунд.
    bot = make_bot()
    user = make_user()
    db = FakeSession()
    already_closed = make_known_trade(close_time="уже закрыта")
    commission = sync_env(user=user, known=(already_closed,))

    # Act
    await _async_bot_trades(db, bot, [make_raw_trade()])  # type: ignore

    # Assert: ни новой записи, ни повторной комиссии
    assert db.added == []
    assert commission.calls == []
    assert user.service_balance == 5000.0
    assert bot.total_profit == 0.0
    assert bot.total_commission_paid_usdt == 0.0


@pytest.mark.asyncio
async def test_open_trade_that_closed_is_updated_and_commission_charged(sync_env):
    # Arrange: сделка была открыта в прошлый опрос, сейчас freqtrade отдал её закрытой
    bot = make_bot()
    user = make_user()
    db = FakeSession()
    open_trade = make_known_trade(close_time=None)
    commission = sync_env(user=user, known=(open_trade,))

    # Act
    await _async_bot_trades(db, bot, [make_raw_trade(profit_abs=20.0, profit_ratio=0.1)])  # type: ignore

    # Assert: обновили существующую запись, а не создали новую
    assert db.added == []
    assert open_trade.profit_usdt == 20.0
    assert open_trade.profit_pct == pytest.approx(10.0)
    assert open_trade.close_rate == 110.0
    assert open_trade.close_time is not None
    assert open_trade.exit_reason == "roi"

    # Комиссия берётся именно в момент закрытия — и ровно один раз
    assert commission.calls == [open_trade]
    assert open_trade.commission_paid is True
    assert user.service_balance == 4820.0  # 5000 - (20 * 0.1 * 90)
    assert bot.total_profit == 20.0
    assert db.commits == 1


@pytest.mark.asyncio
async def test_losing_trade_is_saved_but_charges_no_commission(sync_env):
    # Arrange
    bot = make_bot()
    user = make_user()
    db = FakeSession()
    sync_env(user=user)

    # Act
    await _async_bot_trades(db, bot, [make_raw_trade(profit_abs=-30.0, profit_ratio=-0.15)])  # type: ignore

    # Assert: убыток попадает в статистику и в total_profit, но баланс не трогает
    assert len(db.added) == 1
    assert db.added[0].profit_usdt == -30.0
    assert not db.added[0].commission_paid   # см. комментарий про default=False выше
    assert user.service_balance == 5000.0
    assert bot.total_profit == -30.0


@pytest.mark.asyncio
async def test_short_trade_direction_is_taken_from_is_short(sync_env):
    # Arrange: freqtrade сообщает направление флагом is_short, а не строкой
    bot = make_bot()
    db = FakeSession()
    sync_env(user=make_user())

    # Act
    await _async_bot_trades(db, bot, [make_raw_trade(is_short=True)])  # type: ignore

    # Assert
    assert db.added[0].direction == "short"


@pytest.mark.asyncio
async def test_sync_is_skipped_when_bot_owner_is_missing(sync_env):
    # Arrange
    # Без пользователя комиссию списывать не с кого. Код в этом случае выходит
    # молча, не создавая записей и не коммитя — иначе сделки сохранились бы,
    # а деньги за них не были бы взяты никогда.
    bot = make_bot()
    db = FakeSession()
    sync_env(user=None)

    # Act
    await _async_bot_trades(db, bot, [make_raw_trade()])  # type: ignore

    # Assert
    assert db.added == []
    assert db.commits == 0


@pytest.mark.asyncio
async def test_several_trades_are_processed_in_one_pass(sync_env):
    # Arrange: одна уже известна и закрыта, две новые
    bot = make_bot()
    user = make_user()
    db = FakeSession()
    known = make_known_trade(freqtrade_trade_id=1, close_time="уже закрыта")
    sync_env(user=user, known=(known,))

    # Act
    await _async_bot_trades(  # type: ignore
        db,  # type: ignore
        bot,
        [
            make_raw_trade(trade_id=1, profit_abs=10.0),
            make_raw_trade(trade_id=2, profit_abs=10.0),
            make_raw_trade(trade_id=3, profit_abs=10.0),
        ],
    )

    # Assert: создались только две новые, комиссия списана дважды
    assert [t.freqtrade_trade_id for t in db.added] == [2, 3]
    assert user.service_balance == 4820.0  # 5000 - 2 * (10 * 0.1 * 90)
    assert bot.total_profit == 20.0
    # коммит один на весь пакет, а не на каждую сделку
    assert db.commits == 1
