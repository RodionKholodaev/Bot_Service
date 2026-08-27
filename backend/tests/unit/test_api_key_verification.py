"""
Юнит-тесты проверки биржевого ключа при добавлении.

Раньше ключ сохранялся без единого обращения к бирже: неверный, протухший или
read-only ключ обнаруживался упавшим контейнером — постфактум, и причина была видна
только в логах докера. Теперь ApiKeyService спрашивает биржу до записи в базу.

Проверяется три вещи: что негодный ключ отбит с понятным текстом и НЕ попал в
репозиторий; что недоступность биржи не выдаётся за «ключ неверный» (503, а не 400);
и что ответ биржи о правах разбирается верно, включая неожиданный формат.

Ни сети, ни БД: биржа — FakeExchangeAccountClient, репозиторий — Spy.
"""

from datetime import UTC, datetime, timedelta

import ccxt
import pytest

from src.core.crypto import decrypt, encrypt
from src.core.exceptions import BadRequestError, NotFoundError, ServiceUnavailableError
from src.models.bot import Bot
from src.models.exchange_api_key import ExchangeApiKey
from src.models.user import User
from src.schemas.api_keys import ApiKeyCreate
from src.services.api_keys_service import ApiKeyService
from src.services.exchange_account import KeyPermissions, _translate, parse_bybit_permissions
from tests.fakes.test_exchange_account import FakeExchangeAccountClient

# ──────────────────────────────────────────────
# Фабрики и фейки
# ──────────────────────────────────────────────


def make_user(*, user_id: int = 1) -> User:
    return User(id=user_id, email="test@test.com")


def make_payload(**overrides) -> ApiKeyCreate:
    data = {"name": "Мой Bybit", "exchange": "bybit", "api_key": "key-123", "api_secret": "secret-456"}
    data.update(overrides)
    return ApiKeyCreate(**data)


def make_permissions(**overrides) -> KeyPermissions:
    """Права нормального боевого ключа."""
    data = {"read_only": False, "can_trade_futures": True, "expires_at": None}
    data.update(overrides)
    return KeyPermissions(**data)


class SpyApiKeysRepo:
    """Spy вместо ApiKeysRepository — запоминает записанные ключи, ничего не пишет."""

    def __init__(self, keys: list[ExchangeApiKey] | None = None):
        self.saved: list[dict] = []
        self._keys = keys or []

    async def add_api_key(self, user_id, exchange, label, key_enc, secret_enc):
        self.saved.append(
            {"user_id": user_id, "exchange": exchange, "label": label, "key": key_enc, "secret": secret_enc}
        )
        key = ExchangeApiKey(
            id=1,
            user_id=user_id,
            exchange=exchange,
            label=label,
            api_key_encrypted=key_enc,
            api_secret_encrypted=secret_enc,
            is_active=True,
            created_at=datetime.now(UTC),
        )
        self._keys.append(key)
        return key

    async def get_api_key_by_id(self, key_id, user_id):
        for key in self._keys:
            if key.id == key_id and key.user_id == user_id:
                return key
        return None


class FakeBotRepo:
    """Fake вместо BotRepository — отдаёт заготовленный список ботов на ключе."""

    def __init__(self, bots: list | None = None):
        self.bots = bots or []

    async def get_live_bots_on_key(self, api_key_id, *, exclude_bot_id=None):
        return self.bots


# ──────────────────────────────────────────────
# Ключ проверяется на бирже до сохранения
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_valid_key_is_verified_and_saved_encrypted():
    # Arrange
    repo = SpyApiKeysRepo()
    exchange = FakeExchangeAccountClient(total=250.0)

    # Act
    await ApiKeyService(repo, exchange).create_api_key(make_user(), make_payload())  # type: ignore

    # Assert
    # на биржу сходили за правами и за балансом — одного баланса мало, см. тест ниже
    assert [call[0] for call in exchange.calls] == ["fetch_permissions", "fetch_balance"]
    assert len(repo.saved) == 1
    # в базу ключ уезжает зашифрованным, но расшифровывается обратно в исходный
    assert decrypt(repo.saved[0]["key"]) == "key-123"
    assert decrypt(repo.saved[0]["secret"]) == "secret-456"


@pytest.mark.asyncio
async def test_read_only_key_is_rejected():
    # Arrange
    # Ключ только на чтение прекрасно отдаёт баланс и молча проходил бы проверку
    # одним fetch_balance — а бот на нём не откроет ни одной сделки.
    repo = SpyApiKeysRepo()
    exchange = FakeExchangeAccountClient(permissions=make_permissions(read_only=True))

    # Act / Assert
    with pytest.raises(BadRequestError) as exc:
        await ApiKeyService(repo, exchange).create_api_key(make_user(), make_payload())  # type: ignore

    assert "только на чтение" in exc.value.detail
    # ключ в базу не попал, и за балансом даже не ходили
    assert repo.saved == []
    assert [call[0] for call in exchange.calls] == ["fetch_permissions"]


@pytest.mark.asyncio
async def test_key_without_futures_permission_is_rejected():
    # Arrange
    repo = SpyApiKeysRepo()
    exchange = FakeExchangeAccountClient(permissions=make_permissions(can_trade_futures=False))

    # Act / Assert
    with pytest.raises(BadRequestError) as exc:
        await ApiKeyService(repo, exchange).create_api_key(make_user(), make_payload())  # type: ignore

    assert "деривативами" in exc.value.detail
    assert repo.saved == []


@pytest.mark.asyncio
async def test_expired_key_is_rejected():
    # Arrange
    expired = datetime.now(UTC) - timedelta(days=1)
    repo = SpyApiKeysRepo()
    exchange = FakeExchangeAccountClient(permissions=make_permissions(expires_at=expired))

    # Act / Assert
    with pytest.raises(BadRequestError) as exc:
        await ApiKeyService(repo, exchange).create_api_key(make_user(), make_payload())  # type: ignore

    assert "истёк" in exc.value.detail
    assert repo.saved == []


@pytest.mark.asyncio
async def test_key_expiring_soon_is_accepted():
    # Arrange
    # До конца срока ещё три дня — торговать можно, отказывать не за что
    # (в лог при этом уходит предупреждение).
    repo = SpyApiKeysRepo()
    exchange = FakeExchangeAccountClient(permissions=make_permissions(expires_at=datetime.now(UTC) + timedelta(days=3)))

    # Act
    await ApiKeyService(repo, exchange).create_api_key(make_user(), make_payload())  # type: ignore

    # Assert
    assert len(repo.saved) == 1


@pytest.mark.asyncio
async def test_exchange_outage_does_not_save_the_key():
    # Arrange
    # Биржа не ответила — это не приговор ключу: ответ 503, а не 400, и ключ не
    # сохраняется. Непроверенный ключ в базе — ровно то состояние, которое убирали.
    repo = SpyApiKeysRepo()
    exchange = FakeExchangeAccountClient(permissions_error=ServiceUnavailableError("Биржа сейчас не отвечает"))

    # Act / Assert
    with pytest.raises(ServiceUnavailableError):
        await ApiKeyService(repo, exchange).create_api_key(make_user(), make_payload())  # type: ignore

    assert repo.saved == []


@pytest.mark.asyncio
async def test_unsupported_exchange_is_rejected_without_network_call():
    # Arrange
    # config.template.json всегда пишет "name": "bybit" — ключ другой биржи молча
    # уехал бы в bybit-конфиг, и бот всё равно бы не заработал.
    repo = SpyApiKeysRepo()
    exchange = FakeExchangeAccountClient()

    # Act / Assert
    with pytest.raises(BadRequestError) as exc:
        await ApiKeyService(repo, exchange).create_api_key(make_user(), make_payload(exchange="binance"))  # type: ignore

    assert "Bybit" in exc.value.detail
    assert exchange.calls == []
    assert repo.saved == []


@pytest.mark.asyncio
async def test_key_is_trimmed_and_exchange_normalized():
    # Arrange
    # Пробелы по краям — самая частая порча ключа при копировании из интерфейса биржи.
    repo = SpyApiKeysRepo()
    exchange = FakeExchangeAccountClient()

    # Act
    await ApiKeyService(repo, exchange).create_api_key(  # type: ignore
        make_user(), make_payload(exchange="  ByBit ", api_key="  key-123\n", api_secret=" secret-456 ")
    )

    # Assert
    assert repo.saved[0]["exchange"] == "bybit"
    assert decrypt(repo.saved[0]["key"]) == "key-123"
    # на биржу ушёл уже обрезанный ключ, иначе подпись не сошлась бы
    assert exchange.calls == [("fetch_permissions", "key-123"), ("fetch_balance", "key-123")]


# ──────────────────────────────────────────────
# Перевод ошибок ccxt в ответы сервиса
# ──────────────────────────────────────────────


def test_network_errors_become_503_and_key_errors_become_400():
    # Arrange / Act / Assert
    # Порядок веток в _translate повторяет иерархию ccxt: PermissionDenied наследует
    # AuthenticationError, а таймаут и rate limit — оба NetworkError. Перепутанный
    # порядок здесь означал бы «ваш ключ неверный» при недоступной бирже.
    assert isinstance(_translate(ccxt.AuthenticationError("bad key")), BadRequestError)
    assert isinstance(_translate(ccxt.PermissionDenied("no rights")), BadRequestError)
    assert isinstance(_translate(ccxt.ExchangeError("something")), BadRequestError)

    assert isinstance(_translate(ccxt.RequestTimeout("timeout")), ServiceUnavailableError)
    assert isinstance(_translate(ccxt.RateLimitExceeded("too fast")), ServiceUnavailableError)
    assert isinstance(_translate(ccxt.ExchangeNotAvailable("maintenance")), ServiceUnavailableError)
    # и человеку сказано, что делать: ключ не сохранён, попробовать ещё раз
    assert "Ключ не сохранён" in _translate(ccxt.RequestTimeout("timeout")).detail  # type: ignore[attr-defined]
    # незнакомое исключение тоже не должно превращаться в обвинение ключа
    assert isinstance(_translate(RuntimeError("boom")), ServiceUnavailableError)


def test_permission_denied_message_mentions_ip_whitelist():
    # Arrange / Act
    # Ключ, привязанный к чужому IP, биржа отбивает именно этим классом ошибки —
    # и без подсказки про белый список человек ищет проблему в самом ключе.
    detail = _translate(ccxt.PermissionDenied("ip not allowed")).detail  # type: ignore[attr-defined]

    # Assert
    assert "IP" in detail


# ──────────────────────────────────────────────
# Разбор ответа Bybit о правах
# ──────────────────────────────────────────────


def test_read_only_flag_is_parsed():
    # Arrange / Act
    permissions = parse_bybit_permissions({"result": {"readOnly": 1, "permissions": {"ContractTrade": ["Order"]}}})

    # Assert
    assert permissions.read_only is True


def test_empty_trading_groups_mean_no_futures():
    # Arrange / Act
    permissions = parse_bybit_permissions(
        {"result": {"readOnly": 0, "permissions": {"ContractTrade": [], "Derivatives": [], "Spot": ["SpotTrade"]}}}
    )

    # Assert
    # спотовые права фьючерсным ботам не помогают
    assert permissions.can_trade_futures is False


def test_any_futures_group_is_enough():
    # Arrange / Act
    # Состав групп различается для UTA и классического аккаунта; проверка одной
    # жёстко заданной группы отбивала бы рабочие ключи.
    permissions = parse_bybit_permissions({"result": {"readOnly": 0, "permissions": {"Derivatives": ["Position"]}}})

    # Assert
    assert permissions.can_trade_futures is True


def test_unknown_payload_does_not_reject_the_key():
    # Arrange / Act
    # Ошибка разбора ответа — наша проблема, а не пользователя: трактуем в его пользу.
    permissions = parse_bybit_permissions({"retCode": 0})

    # Assert
    assert permissions.read_only is False
    assert permissions.can_trade_futures is True
    assert permissions.expires_at is None


def test_expiry_is_parsed_as_aware_datetime():
    # Arrange / Act
    permissions = parse_bybit_permissions({"result": {"readOnly": 0, "expiredAt": "2030-01-01T00:00:00Z"}})

    # Assert
    # без tzinfo сравнение с datetime.now(UTC) в verify_key упало бы с TypeError
    assert permissions.expires_at is not None
    assert permissions.expires_at.tzinfo is not None
    assert permissions.expires_at.year == 2030


def test_unparsable_expiry_is_treated_as_no_expiry():
    # Arrange / Act
    permissions = parse_bybit_permissions({"result": {"readOnly": 0, "expiredAt": "никогда"}})

    # Assert
    assert permissions.expires_at is None


# ──────────────────────────────────────────────
# Баланс ключа для интерфейса
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_key_balance_is_returned_for_the_owner():
    # Arrange
    key = ExchangeApiKey(
        id=1,
        user_id=1,
        exchange="bybit",
        label="Мой Bybit",
        api_key_encrypted=encrypt("key"),
        api_secret_encrypted=encrypt("secret"),
        is_active=True,
    )
    repo = SpyApiKeysRepo([key])
    bot_repo = FakeBotRepo([Bot(id="b1", name="SOL", stake_amount=40.0)])
    exchange = FakeExchangeAccountClient(total=100.0, free=60.0)

    # Act
    balance = await ApiKeyService(repo, exchange).get_key_balance(make_user(), 1, bot_repo)  # type: ignore

    # Assert
    assert balance.total == 100.0
    assert balance.reserved == 40.0
    assert balance.available == 60.0  # 100 - 40
    assert [bot.name for bot in balance.bots] == ["SOL"]


@pytest.mark.asyncio
async def test_key_balance_of_another_user_is_not_returned():
    # Arrange
    # id ключа приходит из URL: выборка «по одному id» отдала бы баланс чужого счёта.
    repo = SpyApiKeysRepo([])
    exchange = FakeExchangeAccountClient()

    # Act / Assert
    with pytest.raises(NotFoundError):
        await ApiKeyService(repo, exchange).get_key_balance(make_user(), 1, FakeBotRepo())  # type: ignore

    assert exchange.calls == []
