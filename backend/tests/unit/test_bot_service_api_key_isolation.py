"""
Юнит-тесты BotService.create_bot — принадлежности биржевого ключа пользователю.

api_key_id приходит из тела запроса, поэтому ключ обязан искаться только среди
ключей текущего пользователя. Пока выборка шла по одному id, любой залогиненный
пользователь мог создать бота на чужом ключе (в том числе с dry_run=False) и
торговать с чужого счёта.

Ни БД, ни docker, ни диск здесь не нужны: репозитории заменены фейками, а запись
файлов бота — Spy-классом (настоящий BotFileManager писал бы в BOTS_DATA_DIR).
"""

import pytest

from src.core.crypto import encrypt
from src.core.exceptions import NotFoundError
from src.models.exchange_api_key import ExchangeApiKey
from src.models.user import User
from src.schemas.bot import BotCreate
from src.services import bot_service as bot_service_module
from src.services.bot_service import BotService
from tests.fakes.test_exchange_account import FakeExchangeAccountClient


class FakeApiKeysRepo:
    """Fake вместо ApiKeysRepository — отдаёт ключ, только если совпал и id, и владелец."""

    def __init__(self, keys: list[ExchangeApiKey]):
        self._keys = keys
        self.calls: list[tuple[int, int]] = []

    async def get_api_key_by_id(self, key_id, user_id):
        self.calls.append((key_id, user_id))
        for key in self._keys:
            if key.id == key_id and key.user_id == user_id:
                return key
        return None


class FakeBotRepo:
    """Fake вместо BotRepository — запоминает созданных ботов, порт выдаёт фиксированный."""

    def __init__(self):
        self.created: list = []

    async def get_live_bots_on_key(self, api_key_id, *, exclude_bot_id=None):
        # Занятый капитал здесь не проверяется — на него есть
        # tests/unit/test_capital_guard.py; ключ в этих тестах всегда пустой.
        return []

    async def allocate_port(self):
        return 9000

    async def get_live_bot_on_pair(self, api_key_id, pair, *, statuses=None, exclude_bot_id=None):
        # пара всегда свободна: запрет «один ключ — одна пара» проверяется отдельно,
        # в test_bot_pair_conflict.py
        return None

    async def create(self, bot):
        self.created.append(bot)
        return bot


class SpyFileManager:
    """Spy вместо BotFileManager — вместо записи файлов бота запоминает аргументы."""

    def __init__(self):
        self.calls: list[dict] = []

    async def materialize_bot_files(self, bot, user_id, api_key, api_secret, iternal_api_port, jwt_secret, ws_token):
        self.calls.append({"bot": bot, "user_id": user_id, "api_key": api_key, "api_secret": api_secret})


def make_user(*, user_id: int = 1, service_balance: float = 10_000.0) -> User:
    """Пользователь с минимумом полей — create_bot берёт id и сервисный баланс.

    service_balance задан явно: create_bot сверяет его с порогом
    settings.MIN_SERVICE_BALANCE_RUB, а колоночный default=0.0 на несохранённом
    объекте не применяется — там лежал бы None, и сравнение упало бы на TypeError.
    """
    return User(id=user_id, email="test@test.com", service_balance=service_balance)


def make_api_key(*, key_id: int = 10, owner_id: int = 2) -> ExchangeApiKey:
    """Ключ на бирже, зашифрованный так же, как его кладёт ApiKeyService."""
    return ExchangeApiKey(
        id=key_id,
        user_id=owner_id,
        exchange="bybit",
        label="Ключ соседа",
        api_key_encrypted=encrypt("victim-key"),
        api_secret_encrypted=encrypt("victim-secret"),
        is_active=True,
    )


def make_body(**overrides) -> BotCreate:
    """Валидное тело POST /bots с разумными дефолтами."""
    data = {
        "name": "bot",
        "pair": "XRP/USDT:USDT",
        "leverage": 5,
        "direction": "long",
        "strategy_preset": "moderate",
        # схема требует фильтры даже под пресет — направление long, значит нужен long-набор
        "entry_filters_long": [{"indicator": "rsi", "timeframe": "5m", "condition": "less", "value": 30}],
        "take_profit_percent": 4.0,
        "stop_loss_enabled": True,
        "stop_loss_percent": 2.0,
        "dry_run": False,
        "api_key_id": 10,
        "stake_amount": 100.0,
        "tradable_balance_ratio": 0.5,
    }
    data.update(overrides)
    return BotCreate(**data)


@pytest.mark.asyncio
async def test_bot_creation_rejects_api_key_of_another_user(monkeypatch):
    # Arrange
    spy_files = SpyFileManager()
    monkeypatch.setattr(bot_service_module, "BotFileManager", spy_files)

    attacker = make_user(user_id=1)
    # ключ принадлежит пользователю 2, а бота создаёт пользователь 1
    api_keys_repo = FakeApiKeysRepo([make_api_key(key_id=10, owner_id=2)])
    bot_repo = FakeBotRepo()

    # Act / Assert
    with pytest.raises(NotFoundError):
        await BotService(bot_repo, api_keys_repo, FakeExchangeAccountClient()).create_bot(
            attacker, make_body(api_key_id=10)
        )  # type: ignore

    # ключ искался именно среди ключей запросившего
    assert api_keys_repo.calls == [(10, 1)]
    # и отказ случился до записи в БД и до создания файлов
    assert bot_repo.created == []
    assert spy_files.calls == []


@pytest.mark.asyncio
async def test_bot_creation_rejects_unknown_api_key(monkeypatch):
    # Arrange
    spy_files = SpyFileManager()
    monkeypatch.setattr(bot_service_module, "BotFileManager", spy_files)

    user = make_user(user_id=1)
    api_keys_repo = FakeApiKeysRepo([])
    bot_repo = FakeBotRepo()

    # Act / Assert
    # несуществующий и чужой ключ дают один и тот же ответ: по коду нельзя понять,
    # какие id ключей вообще заняты
    with pytest.raises(NotFoundError):
        await BotService(bot_repo, api_keys_repo, FakeExchangeAccountClient()).create_bot(
            user, make_body(api_key_id=999)
        )  # type: ignore

    assert bot_repo.created == []


@pytest.mark.asyncio
async def test_own_api_key_is_decrypted_and_passed_to_bot_files(monkeypatch):
    # Arrange
    spy_files = SpyFileManager()
    monkeypatch.setattr(bot_service_module, "BotFileManager", spy_files)

    user = make_user(user_id=1)
    api_keys_repo = FakeApiKeysRepo([make_api_key(key_id=10, owner_id=1)])
    bot_repo = FakeBotRepo()

    # Act
    bot = await BotService(bot_repo, api_keys_repo, FakeExchangeAccountClient()).create_bot(
        user, make_body(api_key_id=10)
    )  # type: ignore

    # Assert
    assert bot_repo.created == [bot]
    assert bot.user_id == 1
    # в файлы бота уходит расшифрованная пара ключ/секрет
    assert spy_files.calls[0]["api_key"] == "victim-key"
    assert spy_files.calls[0]["api_secret"] == "victim-secret"


@pytest.mark.asyncio
async def test_bot_without_api_key_is_created_with_empty_credentials(monkeypatch):
    # Arrange
    spy_files = SpyFileManager()
    monkeypatch.setattr(bot_service_module, "BotFileManager", spy_files)

    user = make_user(user_id=1)
    api_keys_repo = FakeApiKeysRepo([])
    bot_repo = FakeBotRepo()

    # Act
    # dry-run бот ключа не требует — в репозиторий за ним ходить не должны вовсе
    await BotService(bot_repo, api_keys_repo, FakeExchangeAccountClient()).create_bot(
        user, make_body(api_key_id=None, dry_run=True)
    )  # type: ignore

    # Assert
    assert api_keys_repo.calls == []
    assert spy_files.calls[0]["api_key"] == ""
    assert spy_files.calls[0]["api_secret"] == ""
