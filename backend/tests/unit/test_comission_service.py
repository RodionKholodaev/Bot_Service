"""
Юнит-тесты для CommissionService.

process_commission — единственное место, где сервис трогает реальные деньги
пользователя (User.service_balance). Поэтому здесь важны не столько «счастливые»
расчёты, сколько границы: сделка в ноль, убыток, недоступный курс и повторный
вызов на той же сделке.

Тесты идут без сети и без БД:
- process_commission — статический метод, работает с уже загруженными объектами;
- ExchangeRateService подменяется фейком (см. фикстуру set_usdt_rate), иначе тест
  ходил бы в интернет за курсом и падал бы вместе с чужим API.
"""

import pytest

from src.models.bot import Bot
from src.models.trade import Trade
from src.models.user import User
from src.services.commission_service import CommissionService


# ──────────────────────────────────────────────
# Вспомогательные фабрики — чтобы в каждом тесте задавать
# только то, что важно именно для него.
# ──────────────────────────────────────────────

def make_trade(
    *,
    profit_usdt: float | None,
    commission_paid: bool = False,
    freqtrade_trade_id: int = 1,
) -> Trade:
    """Сделка в памяти (без записи в БД) с разумными дефолтами."""
    return Trade(
        profit_usdt=profit_usdt,
        commission_paid=commission_paid,
        freqtrade_trade_id=freqtrade_trade_id,
    )


def make_user(*, commission_rate: float = 0.1, service_balance: float = 5000.0) -> User:
    """Пользователь с комиссией 10% и балансом 5000 ₽ — дефолт для расчётов ниже."""
    return User(commission_rate=commission_rate, service_balance=service_balance)


def make_bot(**overrides) -> Bot:
    """Бот с обнулёнными накопительными полями — их и проверяют тесты."""
    defaults = dict(
        total_profit=0.0,
        total_commission_paid_usdt=0.0,
        total_commission_paid_rub=0.0,
    )
    defaults.update(overrides)
    return Bot(**defaults)


class FakeExchangeRateService:
    """Fake вместо реального ExchangeRateService — не ходит в сеть."""

    def __init__(self, rate: float | None):
        self._rate = rate

    async def get_usdt_rub(self):
        return self._rate


@pytest.fixture
def set_usdt_rate(monkeypatch):
    """Подменяет ExchangeRateService фейком с нужным курсом.

    Патчим по пути `src.services.commission_service.ExchangeRateService`, а не по
    месту объявления: commission_service импортировал класс к себе в модуль, и
    подмена в модуле-источнике на уже импортированное имя не подействовала бы.
    """

    def _set(rate: float | None) -> None:
        monkeypatch.setattr(
            "src.services.commission_service.ExchangeRateService",
            lambda: FakeExchangeRateService(rate),
        )

    return _set


# ──────────────────────────────────────────────
# Прибыльная сделка — основной расчёт
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_commission_calculated_correctly_for_profitable_trade(set_usdt_rate):
    # Arrange
    trade = make_trade(profit_usdt=100.0)
    user = make_user()
    bot = make_bot()
    set_usdt_rate(90.0)

    # Act
    await CommissionService.process_commission(trade, user, bot)

    # Assert
    assert bot.total_profit == 100.0
    assert trade.commission_usdt == 10.0          # 100 * 0.1
    assert trade.commission_rub == 900.0          # 10 * 90
    assert trade.commission_paid is True
    assert user.service_balance == 4100.0         # 5000 - 900
    assert bot.total_commission_paid_usdt == 10.0
    assert bot.total_commission_paid_rub == 900.0


# ──────────────────────────────────────────────
# Границы: когда комиссию брать НЕ нужно
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_loss_trade_charges_no_commission(set_usdt_rate):
    # Arrange
    trade = make_trade(profit_usdt=-100.0)
    user = make_user()
    bot = make_bot()
    set_usdt_rate(90.0)

    # Act
    await CommissionService.process_commission(trade, user, bot)

    # Assert: убыток всё равно уходит в накопленный профит бота, но баланс не трогаем
    assert bot.total_profit == -100.0
    # флаг ставится и на убыточной сделке: он означает "сделка уже учтена",
    # а не "комиссия списана" — иначе убыток прибавлялся бы к total_profit
    # заново на каждом опросе бота
    assert trade.commission_paid is True
    assert user.service_balance == 5000.0
    assert bot.total_commission_paid_usdt == 0.0
    assert bot.total_commission_paid_rub == 0.0


@pytest.mark.asyncio
async def test_zero_profit_trade_charges_no_commission(set_usdt_rate):
    # Arrange
    # Сделка, закрытая ровно «в ноль»: комиссия берётся строго с profit > 0.
    # Граница неочевидная — при `profit >= 0` сервис списывал бы 0 ₽, но
    # проставлял commission_paid=True, и сделка выглядела бы обработанной.
    trade = make_trade(profit_usdt=0.0)
    user = make_user()
    bot = make_bot()
    set_usdt_rate(90.0)

    # Act
    await CommissionService.process_commission(trade, user, bot)

    # Assert
    assert bot.total_profit == 0.0
    assert trade.commission_paid is False
    assert user.service_balance == 5000.0
    assert bot.total_commission_paid_usdt == 0.0


@pytest.mark.asyncio
async def test_none_profit_is_treated_as_zero(set_usdt_rate):
    # Arrange
    # profit_usdt=None приходит от freqtrade у ещё не закрытых сделок.
    # Код приводит его к 0.0, а не падает на None.
    trade = make_trade(profit_usdt=None)
    user = make_user()
    bot = make_bot()
    set_usdt_rate(90.0)

    # Act
    await CommissionService.process_commission(trade, user, bot)

    # Assert
    assert bot.total_profit == 0.0
    assert trade.commission_paid is False
    assert user.service_balance == 5000.0


# ──────────────────────────────────────────────
# Защита от повторного списания
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_commission_is_not_charged_twice_for_the_same_trade(set_usdt_rate):
    # Arrange
    # polling_worker крутится каждые 30 секунд и в принципе может увидеть одну и ту же
    # закрытую сделку повторно. Единственный барьер против двойного списания реальных
    # денег — флаг trade.commission_paid, поэтому он проверяется отдельным тестом.
    trade = make_trade(profit_usdt=100.0)
    user = make_user()
    bot = make_bot()
    set_usdt_rate(90.0)

    # Act: обрабатываем одну и ту же сделку дважды
    await CommissionService.process_commission(trade, user, bot)
    await CommissionService.process_commission(trade, user, bot)

    # Assert: с баланса списано ровно один раз
    assert user.service_balance == 4100.0
    assert trade.commission_usdt == 10.0
    assert trade.commission_rub == 900.0
    assert bot.total_commission_paid_usdt == 10.0
    assert bot.total_commission_paid_rub == 900.0

    # А вот total_profit защиты не имеет и досчитывает прибыль второй раз.
    # Это текущее поведение кода, а не желаемое: в проде спасает только то, что
    # polling_worker вызывает process_commission один раз — в момент перехода
    # сделки в закрытые (см. _async_bot_trades). Тест фиксирует факт, чтобы
    # расхождение Bot.total_profit с суммой Trade.profit_usdt не стало сюрпризом.
    assert bot.total_profit == 200.0


@pytest.mark.asyncio
async def test_already_paid_trade_does_not_touch_balance(set_usdt_rate):
    # Arrange: сделка пришла уже помеченной как оплаченная
    trade = make_trade(profit_usdt=100.0, commission_paid=True)
    user = make_user()
    bot = make_bot()
    set_usdt_rate(90.0)

    # Act
    await CommissionService.process_commission(trade, user, bot)

    # Assert
    assert user.service_balance == 5000.0
    assert bot.total_commission_paid_usdt == 0.0
    assert bot.total_commission_paid_rub == 0.0


# ──────────────────────────────────────────────
# Недоступный курс USDT/RUB
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_missing_exchange_rate_raises(set_usdt_rate):
    # Arrange
    # Без курса комиссию в рублях посчитать нельзя. Списать «примерно» нельзя тем более,
    # поэтому сервис выбрасывает ValueError, а polling_worker откатывает транзакцию.
    trade = make_trade(profit_usdt=50.0)
    user = make_user()
    bot = make_bot()
    set_usdt_rate(None)

    # Act / Assert
    with pytest.raises(ValueError):
        await CommissionService.process_commission(trade, user, bot)

    # сделка НЕ помечена обработанной: исключение откатит транзакцию целиком,
    # и следующий цикл воркера должен посчитать её заново
    assert trade.commission_paid is False


@pytest.mark.asyncio
async def test_second_call_does_not_count_the_trade_twice(monkeypatch):
    # Повторный вызов возможен: например, если у закрытой сделки не разобралась дата
    # закрытия, воркер каждые 30 секунд видел её как "только что закрывшуюся".
    # Раньше bot.total_profit прибавлялся без всякой проверки и накручивался бесконечно.

    # Arrange
    trade = Trade(profit_usdt=100.0, commission_paid=False, freqtrade_trade_id=1)
    user = User(commission_rate=0.1, service_balance=5000.0)
    bot = Bot(
        total_profit=0.0,
        total_commission_paid_usdt=0.0,
        total_commission_paid_rub=0.0,
    )
    monkeypatch.setattr(
        "src.services.commission_service.ExchangeRateService",
        lambda: FakeExchangeRateService(rate=90.0),
    )

    # Act
    await CommissionService.process_commission(trade, user, bot)
    await CommissionService.process_commission(trade, user, bot)

    # Assert: всё осталось таким же, как после одного вызова
    assert bot.total_profit == 100.0
    assert bot.total_commission_paid_usdt == 10.0
    assert user.service_balance == 4100.0


    # При этом bot.total_profit успел обновиться до выброса исключения — объект в
    # памяти остаётся «грязным». В проде это чинит db.rollback() в polling_worker,
    # но при прямом вызове сервиса про это нужно помнить.
    assert bot.total_profit == 50.0
