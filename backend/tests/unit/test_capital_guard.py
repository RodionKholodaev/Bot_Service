"""
Юнит-тесты capital_guard — сколько денег на биржевом ключе свободно под нового бота.

Депозит каждого бота уезжает в его config.json как available_capital, и до этой
проверки депозиты разных ботов на одном ключе ни с чем не сверялись: на счёте в
40 USDT можно было создать бота SOL с депозитом 40 и бота BTC с депозитом 40 — пары
разные, запрет «один ключ — одна пара» пройден, оба вошли, счёт в ноль.

Главное, что здесь зафиксировано: считаем от total, а не от free. free биржа уже
уменьшила на маржу открытых позиций, и вычитание депозитов из него посчитало бы те же
деньги дважды.

Сети нет: биржа — FakeExchangeAccountClient.
"""

import pytest

from src.core.crypto import encrypt
from src.models.bot import Bot
from src.models.exchange_api_key import ExchangeApiKey
from src.services import capital_guard
from tests.fakes.test_exchange_account import FakeExchangeAccountClient

# ──────────────────────────────────────────────
# Фабрики
# ──────────────────────────────────────────────


def make_api_key(*, key_id: int = 10, label: str = "Мой Bybit") -> ExchangeApiKey:
    return ExchangeApiKey(
        id=key_id,
        user_id=1,
        exchange="bybit",
        label=label,
        api_key_encrypted=encrypt("key"),
        api_secret_encrypted=encrypt("secret"),
        is_active=True,
    )


def make_bot(*, bot_id: str = "b1", name: str = "SOL", stake_amount: float = 40.0) -> Bot:
    return Bot(id=bot_id, name=name, stake_amount=stake_amount)


# ──────────────────────────────────────────────
# Арифметика
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_available_is_total_minus_reserved():
    # Arrange
    exchange = FakeExchangeAccountClient(total=100.0)

    # Act
    capital = await capital_guard.get_key_capital(exchange, make_api_key(), [make_bot(stake_amount=40.0)])

    # Assert
    assert capital.reserved == 40.0
    assert capital.available == 60.0  # 100 - 40


@pytest.mark.asyncio
async def test_reserved_is_counted_from_total_not_free():
    # Arrange
    # Бот с депозитом 40 уже в позиции: биржа сама убрала эти деньги из free.
    # Если считать от free, депозит вычтется вторично (0 - 40 = -40), и создать
    # второго бота будет нельзя даже там, где деньги на него есть.
    exchange = FakeExchangeAccountClient(total=100.0, free=60.0)

    # Act
    capital = await capital_guard.get_key_capital(exchange, make_api_key(), [make_bot(stake_amount=40.0)])

    # Assert
    assert capital.available == 60.0  # 100 - 40, а не 60 - 40
    assert capital.free == 60.0  # free при этом отдаётся интерфейсу как есть


@pytest.mark.asyncio
async def test_reserved_sums_all_bots_on_the_key():
    # Arrange
    exchange = FakeExchangeAccountClient(total=100.0)
    bots = [make_bot(bot_id="b1", stake_amount=40.0), make_bot(bot_id="b2", stake_amount=35.0)]

    # Act
    capital = await capital_guard.get_key_capital(exchange, make_api_key(), bots)

    # Assert
    assert capital.reserved == 75.0
    assert capital.available == 25.0  # 100 - 40 - 35


@pytest.mark.asyncio
async def test_available_can_be_negative():
    # Arrange
    # Боты созданы до появления этой проверки или деньги вывели со счёта уже после.
    # Обрезать такое до нуля нельзя: цифра в тексте отказа должна быть настоящей.
    exchange = FakeExchangeAccountClient(total=10.0)

    # Act
    capital = await capital_guard.get_key_capital(exchange, make_api_key(), [make_bot(stake_amount=40.0)])

    # Assert
    assert capital.available == -30.0


def test_exact_fit_is_enough():
    # Arrange
    # Депозит ровно в размер свободного капитала — законная ситуация: «весь счёт
    # одному боту». Отказ здесь означал бы, что весь баланс потратить нельзя.
    capital = capital_guard.KeyCapital(total=40.0, free=40.0, reserved=0.0, available=40.0, bots=[])

    # Act / Assert
    assert capital_guard.is_enough(capital, 40.0) is True
    # цент сверх свободного капитала прощается (допуск на погрешность float),
    # рубль — уже нет
    assert capital_guard.is_enough(capital, 40.01) is True
    assert capital_guard.is_enough(capital, 41.0) is False


def test_float_noise_does_not_cause_a_false_refusal():
    # Arrange
    # 100 - 33.3 - 33.3 - 33.3 = 0.10000000000000853, а не 0.1 — без допуска в один
    # цент «ровно впритык» иногда оказывается ложью на ровном месте.
    available = 100.0 - 33.3 - 33.3 - 33.3
    capital = capital_guard.KeyCapital(total=100.0, free=100.0, reserved=99.9, available=available, bots=[])

    # Act / Assert
    assert capital_guard.is_enough(capital, 0.1) is True


# ──────────────────────────────────────────────
# Текст отказа
# ──────────────────────────────────────────────


def test_refusal_message_names_the_numbers_and_the_rival_bot():
    # Arrange
    capital = capital_guard.KeyCapital(
        total=40.0,
        free=0.0,
        reserved=40.0,
        available=0.0,
        bots=[capital_guard.BotReservation(id="b1", name="SOL", stake_amount=40.0)],
    )

    # Act
    message = capital_guard.not_enough_capital_message("Мой Bybit", capital, 40.0)

    # Assert
    # человек должен увидеть три цифры: сколько на ключе, чем занято, сколько нужно
    assert "40 USDT" in message
    assert "«SOL»" in message
    assert "Мой Bybit" in message


def test_refusal_message_without_bots_does_not_list_them():
    # Arrange
    # Ботов нет, денег просто мало — фразы «занято ботами» тут быть не должно.
    capital = capital_guard.KeyCapital(total=5.0, free=5.0, reserved=0.0, available=5.0, bots=[])

    # Act
    message = capital_guard.not_enough_capital_message("Мой Bybit", capital, 40.0)

    # Assert
    assert "занято ботами" not in message
    assert "5 USDT" in message


# ──────────────────────────────────────────────
# Кэш баланса
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_balance_is_cached_between_calls():
    # Arrange
    # Форма создания бота спрашивает баланс, следом POST /bots считает его же —
    # без кэша это два одинаковых запроса к бирже подряд.
    exchange = FakeExchangeAccountClient(total=100.0)
    api_key = make_api_key()

    # Act
    await capital_guard.get_key_capital(exchange, api_key, [])
    await capital_guard.get_key_capital(exchange, api_key, [])

    # Assert
    assert len(exchange.calls) == 1


@pytest.mark.asyncio
async def test_cache_is_per_key():
    # Arrange
    # Кэш общий на процесс: без разделения по id ключа баланс одного пользователя
    # подставился бы другому.
    exchange = FakeExchangeAccountClient(total=100.0)

    # Act
    await capital_guard.get_key_capital(exchange, make_api_key(key_id=10), [])
    await capital_guard.get_key_capital(exchange, make_api_key(key_id=11), [])

    # Assert
    assert len(exchange.calls) == 2
