import logging

import httpx
import pytest

from src.models.bot import Bot
from src.services import docker_manager
from src.services.polling_worker import (
    MAX_PING_MISSES,
    _check_and_sync_bot,
    _ping_bot,
)

PING = "/api/v1/ping"
SHOW_CONFIG = "/api/v1/show_config"
TRADES = "/api/v1/trades"

# НЕ ПРОВЕРЯЛ ЭТОТ КОД!!!
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
    """Fake вместо AsyncSession — считает коммиты, больше ничего не делает."""

    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1

    async def flush(self):
        pass

    async def refresh(self, obj):
        pass


def make_bot() -> Bot:
    return Bot(
        id="bot-1",
        user_id=1,
        status="running",
        container_id="container-1",
        api_port=9000,
        api_username="user",
        api_password="pass",
    )


@pytest.fixture
def stopped_containers(monkeypatch):
    """Подменяет docker_manager — тесты не трогают реальный Docker."""
    stopped: list[str] = []
    monkeypatch.setattr(docker_manager, "get_container_status", lambda cid: "running")
    monkeypatch.setattr(
        docker_manager, "get_container_logs", lambda cid, tail=50: "Could not load markets"
    )
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
