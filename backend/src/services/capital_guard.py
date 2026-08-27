"""
Хватает ли денег на биржевом ключе под ещё одного бота.

Каждый бот пишет свой депозит в config.json как available_capital, и до сих пор эти
депозиты ни с чем не сверялись. Изолированная маржа тут не помогает: она разводит риск
по позициям, но открываются они из одного кошелька. На счёте 40 USDT можно было
создать бота на SOL с депозитом 40 и бота на BTC с депозитом 40 — пары разные, запрет
«один ключ — одна пара» пройден, оба вошли, счёт в ноль, дальше ордера отбивает биржа.
Наружу это не видно вообще: ping отвечает, статус RUNNING, в интерфейсе всё хорошо.

Формула:

    reserved  = сумма Bot.stake_amount живых боевых ботов на этом ключе
    available = balance.total - reserved

Считаем от total, а не от free, и это главное решение здесь. free биржа уже уменьшила
на маржу открытых позиций, то есть депозит уже торгующего бота вычтен из него биржей —
вычитая reserved из free, мы посчитали бы те же деньги дважды и не дали бы создать
второго бота там, где деньги на него есть.

«Живой бот» — неархивированный боевой бот на этом ключе, в любом статусе. Остановленный
или упавший бот тоже может держать открытую позицию, его депозит по-прежнему занят —
ровно та же логика, что и в запрете «один ключ — одна пара» (bot_service).
"""

import logging
import time
from dataclasses import dataclass

from src.core.crypto import decrypt
from src.models.bot import Bot
from src.models.exchange_api_key import ExchangeApiKey
from src.services.exchange_account import AccountBalance, ExchangeAccountClient

logger = logging.getLogger(__name__)

# Форма создания бота спрашивает баланс, а следом POST /bots считает его же. Кэш
# на несколько секунд убирает второй поход на биржу; процесс бэкенда один, словаря
# достаточно.
BALANCE_CACHE_TTL = 15.0

_balance_cache: dict[int, tuple[float, AccountBalance]] = {}


@dataclass(frozen=True)
class BotReservation:
    """Сколько занимает один уже существующий бот."""

    id: str
    name: str
    stake_amount: float


@dataclass(frozen=True)
class KeyCapital:
    """Раскладка капитала одного биржевого ключа, в USDT."""

    total: float
    free: float
    reserved: float
    available: float
    bots: list[BotReservation]


def clear_balance_cache() -> None:
    """Сбросить кэш целиком. Нужен тестам и на случай ручной отладки."""
    _balance_cache.clear()


async def fetch_balance_cached(client: ExchangeAccountClient, api_key: ExchangeApiKey) -> AccountBalance:
    """Баланс ключа с коротким кэшем по id ключа."""
    cached = _balance_cache.get(api_key.id)
    # нынешнее время
    now = time.monotonic()
    # если кеш молодой (не более 15 секунд отроду), то мы его возвращаем
    # а если старый, то обновляем
    if cached is not None and now - cached[0] < BALANCE_CACHE_TTL:
        return cached[1]
    # получаем новый баланс
    balance = await client.fetch_balance(
        api_key.exchange,
        decrypt(api_key.api_key_encrypted),
        decrypt(api_key.api_secret_encrypted),
    )
    # обновляем кеш
    _balance_cache[api_key.id] = (now, balance)
    return balance


async def get_key_capital(
    client: ExchangeAccountClient,
    api_key: ExchangeApiKey,
    live_bots: list[Bot],
) -> KeyCapital:
    """Баланс ключа минус депозиты уже существующих на нём ботов."""
    balance = await fetch_balance_cached(client, api_key)

    reservations = [
        BotReservation(id=bot.id, name=bot.name, stake_amount=float(bot.stake_amount or 0.0)) for bot in live_bots
    ]
    reserved = sum(item.stake_amount for item in reservations)

    return KeyCapital(
        total=balance.total,
        free=balance.free,
        reserved=reserved,
        # Отрицательное available — нормальное состояние: боты могли быть созданы до
        # этой проверки или пользователь вывел деньги со счёта. Ноль тут врал бы.
        available=balance.total - reserved,
        bots=reservations,
    )


def _money(value: float) -> str:
    """40.0 -> "40", 12.5 -> "12.5" — числа в тексте отказа читает человек."""
    return f"{round(value, 2):g}"


def not_enough_capital_message(key_label: str, capital: KeyCapital, requested: float) -> str:
    """Текст отказа с цифрами: сколько на ключе, чем занято, сколько осталось."""
    head = f"На ключе «{key_label}» {_money(capital.total)} USDT"

    if capital.bots:
        listed = ", ".join(f"«{item.name}» — {_money(item.stake_amount)} USDT" for item in capital.bots)
        head += f", из них {_money(capital.reserved)} уже занято ботами: {listed}"

    return (
        f"{head}. Свободно {_money(max(capital.available, 0.0))} USDT, "
        f"а этому боту нужно {_money(requested)} USDT. "
        "Уменьшите депозит, удалите лишнего бота или пополните счёт на бирже."
    )


def is_enough(capital: KeyCapital, requested: float) -> bool:
    """Депозит ровно в размер свободного капитала — уже достаточно.

    Допуск в один цент закрывает погрешность float на сложении депозитов: без него
    «40 - 20 - 20 >= 0» иногда оказывается ложью.
    """
    return capital.available + 0.01 >= requested
