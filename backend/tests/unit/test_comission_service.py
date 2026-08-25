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
    defaults = {
        "total_profit": 0.0,
        "total_commission_paid_usdt": 0.0,
        "total_commission_paid_rub": 0.0,
    }
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
    assert trade.commission_usdt == 10.0  # 100 * 0.1
    assert trade.commission_rub == 900.0  # 10 * 90
    assert trade.commission_paid is True
    assert user.service_balance == 4100.0  # 5000 - 900
    assert bot.total_commission_paid_usdt == 10.0
    assert bot.total_commission_paid_rub == 900.0
    # Курс, по которому посчитаны рубли, обязан осесть в сделке: ExchangeRateService
    # отдаёт текущий курс, и без этой записи подтвердить списание задним числом нечем.
    # Все 1722 сделки на сервере лежат с NULL в этой колонке — тест держит починку.
    assert trade.exchange_rate_rub_usdt == 90.0


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
    # Курса тоже нет: по убыточной сделке его не запрашивали и списания не было
    assert trade.exchange_rate_rub_usdt is None


@pytest.mark.asyncio
async def test_zero_profit_trade_charges_no_commission(set_usdt_rate):
    # Arrange
    # Сделка, закрытая ровно «в ноль»: комиссия берётся строго с profit > 0,
    # поэтому баланс не двигается. А вот обработанной сделка всё равно
    # помечается — иначе воркер видел бы её незачтённой каждый цикл.
    trade = make_trade(profit_usdt=0.0)
    user = make_user()
    bot = make_bot()
    set_usdt_rate(90.0)

    # Act
    await CommissionService.process_commission(trade, user, bot)

    # Assert
    assert bot.total_profit == 0.0
    assert trade.commission_paid is True
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
    # ноль — не прибыль, комиссии нет; но сделка всё равно учтена
    assert trade.commission_paid is True
    assert user.service_balance == 5000.0


# ──────────────────────────────────────────────
# Защита от повторного списания
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_commission_is_not_charged_twice_for_the_same_trade(set_usdt_rate):
    # Arrange
    # polling_worker крутится каждые 30 секунд и в принципе может увидеть одну и ту же
    # закрытую сделку повторно — например, если у неё не разобралась дата закрытия и
    # каждый цикл она выглядит «только что закрывшейся». Единственный барьер против
    # двойного списания реальных денег — флаг trade.commission_paid, поэтому он
    # проверяется отдельным тестом.
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

    # total_profit тоже не удваивается: ранний return по commission_paid стоит до
    # его обновления. Раньше профит прибавлялся без всякой проверки и на повторных
    # вызовах накручивался бесконечно — этот ассерт держит защиту на месте.
    assert bot.total_profit == 100.0


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

    # Баланс не тронут, сделка не помечена обработанной: исключение откатит
    # транзакцию целиком, и следующий цикл воркера должен посчитать её заново
    assert user.service_balance == 5000.0
    assert trade.commission_paid is False

    # При этом bot.total_profit успел обновиться до выброса исключения — объект в
    # памяти остаётся «грязным». В проде это чинит db.rollback() в polling_worker,
    # но при прямом вызове сервиса про это нужно помнить.
    assert bot.total_profit == 50.0
