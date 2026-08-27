"""
Юнит-тесты BotService: депозит нового бота сверяется с деньгами на биржевом ключе.

Что ловится: на счёте 40 USDT бот SOL с депозитом 40 и бот BTC с депозитом 40 — пары
разные, запрет «один ключ — одна пара» пройден, оба вошли, счёт в ноль, дальше ордера
отбивает биржа. Наружу это не видно: ping отвечает, статус running, в интерфейсе бот
работает.

Здесь проверяется поведение сервиса: когда он вообще спрашивает биржу, что делает с
ответом и — отдельно — как ведёт себя при недоступной бирже, потому что на создании и
на запуске это намеренно разное поведение. Сама арифметика проверяется в
tests/unit/test_capital_guard.py.

Ни сети, ни БД, ни docker: биржа и репозитории — фейки, запись файлов — Spy.
"""

import pytest

from src.core.crypto import encrypt
from src.core.exceptions import ConflictError, ServiceUnavailableError
from src.models.bot import Bot
from src.models.exchange_api_key import ExchangeApiKey
from src.models.user import User
from src.schemas.bot import BotCreate
from src.services import bot_service as bot_service_module
from src.services import docker_manager
from src.services.bot_service import BotService
from tests.fakes.test_exchange_account import FakeExchangeAccountClient

PAIR = "SOL/USDT:USDT"


# ──────────────────────────────────────────────
# Фабрики и фейки
# ──────────────────────────────────────────────


def make_user(*, user_id: int = 1) -> User:
    """Баланс задан явно: create_bot сверяет его с порогом, на None сравнение упало бы."""
    return User(id=user_id, email="test@test.com", service_balance=10_000.0)


def make_api_key(*, key_id: int = 10, owner_id: int = 1) -> ExchangeApiKey:
    return ExchangeApiKey(
        id=key_id,
        user_id=owner_id,
        exchange="bybit",
        label="Мой Bybit",
        api_key_encrypted=encrypt("key"),
        api_secret_encrypted=encrypt("secret"),
        is_active=True,
    )


def make_bot(**overrides) -> Bot:
    """Уже существующий боевой бот — тот, чей депозит занимает капитал ключа."""
    defaults = {
        "id": "rival",
        "user_id": 1,
        "name": "SOL",
        "pair": PAIR,
        "api_key_id": 10,
        "dry_run": False,
        "status": "running",
        "stake_amount": 40.0,
    }
    defaults.update(overrides)
    return Bot(**defaults)


def make_body(**overrides) -> BotCreate:
    """Валидное тело POST /bots: боевой бот с депозитом 40 USDT на ключе №10."""
    data = {
        "name": "Новый бот",
        "pair": "BTC/USDT:USDT",
        "leverage": 5,
        "direction": "long",
        "strategy_preset": "moderate",
        "entry_filters_long": [{"indicator": "rsi", "timeframe": "5m", "condition": "less", "value": 30}],
        "take_profit_percent": 4.0,
        "stop_loss_enabled": True,
        "stop_loss_percent": 2.0,
        "dry_run": False,
        "api_key_id": 10,
        "stake_amount": 40.0,
        "tradable_balance_ratio": 0.5,
    }
    data.update(overrides)
    return BotCreate(**data)


class FakeBotRepo:
    """Fake вместо BotRepository — отдаёт заготовленных ботов ключа и помнит запросы.

    Настоящий SQL-фильтр здесь не воспроизводится: на него есть интеграционный тест
    tests/integration/test_bot_capital_repository.py. Здесь важны аргументы запроса.
    """

    def __init__(self, bots_on_key: list[Bot] | None = None):
        self.bots_on_key = bots_on_key or []
        self.key_queries: list[dict] = []
        self.created: list[Bot] = []
        self.statuses: list[str] = []

    async def get_live_bots_on_key(self, api_key_id, *, exclude_bot_id=None):
        self.key_queries.append({"api_key_id": api_key_id, "exclude_bot_id": exclude_bot_id})
        return [bot for bot in self.bots_on_key if bot.id != exclude_bot_id]

    async def get_live_bot_on_pair(self, api_key_id, pair, *, statuses=None, exclude_bot_id=None):
        # пара всегда свободна: запрет «один ключ — одна пара» проверяется отдельно,
        # в test_bot_pair_conflict.py
        return None

    async def allocate_port(self):
        return 9000

    async def create(self, bot):
        self.created.append(bot)
        return bot

    async def get_user(self, user_id):
        return make_user(user_id=user_id)

    async def change_bot_status(self, status, bot):
        self.statuses.append(status)
        bot.status = status
        return bot

    async def add_error_message(self, error, bot):
        bot.error_message = error
        return bot

    async def change_container_id(self, container_id, bot):
        bot.container_id = container_id
        return bot


class FakeApiKeysRepo:
    """Fake вместо ApiKeysRepository — отдаёт ключ, только если совпал и id, и владелец."""

    def __init__(self, keys: list[ExchangeApiKey]):
        self._keys = keys

    async def get_api_key_by_id(self, key_id, user_id):
        for key in self._keys:
            if key.id == key_id and key.user_id == user_id:
                return key
        return None


class SpyFileManager:
    """Spy вместо BotFileManager — вместо записи файлов бота запоминает вызовы."""

    def __init__(self):
        self.calls: list[dict] = []

    async def materialize_bot_files(self, bot, user_id, api_key, api_secret, iternal_api_port, jwt_secret, ws_token):
        self.calls.append({"bot": bot, "user_id": user_id})


@pytest.fixture
def spy_files(monkeypatch):
    """Подменяет BotFileManager внутри bot_service — тесты не пишут на диск.

    Патчим по пути `src.services.bot_service.BotFileManager`: модуль импортировал имя
    к себе, и подмена в модуле-источнике не подействовала бы.
    """
    spy = SpyFileManager()
    monkeypatch.setattr(bot_service_module, "BotFileManager", spy)
    return spy


@pytest.fixture
def fake_docker(monkeypatch, tmp_path):
    """Заглушки для start_bot: настоящие docker и файлы бота в юнит-тестах не нужны."""
    monkeypatch.setattr(bot_service_module.settings, "BOTS_DATA_DIR", tmp_path)
    monkeypatch.setattr(docker_manager, "ensure_image", lambda: None)
    monkeypatch.setattr(
        docker_manager,
        "run_bot_container",
        lambda container_name, bot_data_dir, api_port_external: type("C", (), {"id": "container-1"})(),
    )

    def prepare(bot_id: str):
        (tmp_path / bot_id).mkdir(exist_ok=True)
        (tmp_path / bot_id / "config.json").write_text("{}", encoding="utf-8")

    return prepare


# ──────────────────────────────────────────────
# Создание бота
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bot_is_rejected_when_key_capital_is_taken(spy_files):
    # Arrange
    # На ключе 40 USDT, и все 40 уже отданы боту SOL. Новый бот на BTC с депозитом 40
    # раньше создавался без единого вопроса — пары-то разные.
    bot_repo = FakeBotRepo(bots_on_key=[make_bot(stake_amount=40.0)])
    exchange = FakeExchangeAccountClient(total=40.0)

    # Act / Assert
    # 409, а не 400: запрос валиден, мешает состояние счёта
    with pytest.raises(ConflictError) as exc:
        await BotService(bot_repo, FakeApiKeysRepo([make_api_key()]), exchange).create_bot(  # type: ignore
            make_user(), make_body(stake_amount=40.0)
        )

    # в тексте — цифры и имя занявшего бота
    assert "40" in exc.value.detail
    assert "«SOL»" in exc.value.detail
    # отказ случился до записи в БД и до создания файлов
    assert bot_repo.created == []
    assert spy_files.calls == []


@pytest.mark.asyncio
async def test_bot_is_created_when_capital_is_enough(spy_files):
    # Arrange
    # 100 USDT на ключе, 40 занято, просят ровно 60 — впритык, но законно.
    bot_repo = FakeBotRepo(bots_on_key=[make_bot(stake_amount=40.0)])
    exchange = FakeExchangeAccountClient(total=100.0)

    # Act
    bot = await BotService(bot_repo, FakeApiKeysRepo([make_api_key()]), exchange).create_bot(  # type: ignore
        make_user(), make_body(stake_amount=60.0)
    )

    # Assert
    assert bot_repo.created == [bot]
    assert len(spy_files.calls) == 1
    # у создаваемого бота нечего исключать из резерва — его ещё нет в базе
    assert bot_repo.key_queries == [{"api_key_id": 10, "exclude_bot_id": None}]


@pytest.mark.asyncio
async def test_dry_run_bot_does_not_ask_the_exchange(spy_files):
    # Arrange
    # Симуляция реальных денег со счёта не берёт — спрашивать биржу не о чем.
    bot_repo = FakeBotRepo(bots_on_key=[make_bot(stake_amount=40.0)])
    exchange = FakeExchangeAccountClient(total=0.0)

    # Act
    await BotService(bot_repo, FakeApiKeysRepo([make_api_key()]), exchange).create_bot(  # type: ignore
        make_user(), make_body(dry_run=True, stake_amount=1000.0)
    )

    # Assert
    assert exchange.calls == []
    assert bot_repo.key_queries == []


@pytest.mark.asyncio
async def test_bot_without_api_key_does_not_ask_the_exchange(spy_files):
    # Arrange
    # Без ключа спрашивать нечего и не у кого: биржевого счёта у такого бота нет.
    bot_repo = FakeBotRepo()
    exchange = FakeExchangeAccountClient(total=0.0)

    # Act
    await BotService(bot_repo, FakeApiKeysRepo([]), exchange).create_bot(  # type: ignore
        make_user(), make_body(api_key_id=None, dry_run=True)
    )

    # Assert
    assert exchange.calls == []


@pytest.mark.asyncio
async def test_creation_fails_when_exchange_is_unreachable(spy_files):
    # Arrange
    # На создании лучше отказ, чем непроверенный депозит: 503 и ничего не записано.
    bot_repo = FakeBotRepo()
    exchange = FakeExchangeAccountClient(balance_error=ServiceUnavailableError("Биржа сейчас не отвечает"))

    # Act / Assert
    with pytest.raises(ServiceUnavailableError):
        await BotService(bot_repo, FakeApiKeysRepo([make_api_key()]), exchange).create_bot(  # type: ignore
            make_user(), make_body()
        )

    assert bot_repo.created == []
    assert spy_files.calls == []


# ──────────────────────────────────────────────
# Запуск уже созданного бота
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_excludes_the_bot_itself_from_the_reserve(fake_docker):
    # Arrange
    # Депозит запускаемого бота уже лежит в БД. Без exclude_bot_id он увидел бы в
    # занятом собственные 40 USDT и не стартовал бы никогда.
    bot = make_bot(id="me", name="BTC", status="stopped", container_id="c1", stake_amount=40.0)
    bot_repo = FakeBotRepo(bots_on_key=[bot])
    exchange = FakeExchangeAccountClient(total=40.0)
    fake_docker(bot.id)

    # Act
    await BotService(bot_repo, FakeApiKeysRepo([make_api_key()]), exchange).start_bot(bot)  # type: ignore

    # Assert
    assert bot.status == "running"
    assert bot_repo.key_queries == [{"api_key_id": 10, "exclude_bot_id": "me"}]


@pytest.mark.asyncio
async def test_start_is_rejected_when_capital_is_taken_by_others(fake_docker):
    # Arrange
    # Пока бот стоял, весь капитал ключа занял другой бот — запускать нечем.
    bot = make_bot(id="me", name="BTC", status="stopped", container_id="c1", stake_amount=40.0)
    bot_repo = FakeBotRepo(bots_on_key=[bot, make_bot(id="rival", name="SOL", stake_amount=40.0)])
    exchange = FakeExchangeAccountClient(total=40.0)
    fake_docker(bot.id)

    # Act / Assert
    with pytest.raises(ConflictError):
        await BotService(bot_repo, FakeApiKeysRepo([make_api_key()]), exchange).start_bot(bot)  # type: ignore

    # Статус не тронут: проверка стоит до перевода в "starting", иначе отбитый бот
    # завис бы в этом статусе.
    assert bot_repo.statuses == []
    assert bot.status == "stopped"


@pytest.mark.asyncio
async def test_start_proceeds_when_exchange_is_unreachable(fake_docker):
    # Arrange
    # На запуске поведение намеренно другое, чем на создании: депозит этого бота уже
    # проверяли при создании, сумма чужих резервов с тех пор не выросла, а блокировать
    # перезапуск из-за минутной недоступности биржи — хуже, чем один раз не пересчитать.
    bot = make_bot(id="me", name="BTC", status="stopped", container_id="c1")
    bot_repo = FakeBotRepo(bots_on_key=[bot])
    exchange = FakeExchangeAccountClient(balance_error=ServiceUnavailableError("Биржа сейчас не отвечает"))
    fake_docker(bot.id)

    # Act
    await BotService(bot_repo, FakeApiKeysRepo([make_api_key()]), exchange).start_bot(bot)  # type: ignore

    # Assert
    assert bot.status == "running"
