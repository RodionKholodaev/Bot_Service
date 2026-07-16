import pytest

from src.services.commission_service import CommissionService
from src.models.bot import Bot
from src.models.user import User
from src.models.trade import Trade


class FakeExchangeRateService:
    """Fake вместо реального ExchangeRateService — не ходит в сеть."""

    def __init__(self, rate: float|None):
        self._rate = rate

    async def get_usdt_rub(self):
        return self._rate


@pytest.mark.asyncio
async def test_commission_calculated_correctly_for_profitable_trade(monkeypatch):
    # monkeypatch - встроенная фикстура pytest

    # тест написан по структуре arrange-act-assert

    # Arrange
    trade = Trade(profit_usdt=100.0, commission_paid=False, freqtrade_trade_id=1)
    user = User(commission_rate=0.1, service_balance=5000.0)
    bot = Bot(
        total_profit=0.0,
        total_commission_paid_usdt=0.0,
        total_commission_paid_rub=0.0,
    )

    # Подменяем ExchangeRateService на fake с фиксированным курсом
    monkeypatch.setattr(
        "src.services.commission_service.ExchangeRateService",
        lambda: FakeExchangeRateService(rate=90.0),
    )

    # Act
    await CommissionService.process_commission(trade, user, bot)

    # Assert
    assert bot.total_profit == 100.0
    assert trade.commission_usdt == 10.0
    assert trade.commission_rub == 900.0
    assert trade.commission_paid is True
    assert user.service_balance == 4100.0  # 5000 - 10*90
    assert bot.total_commission_paid_usdt == 10.0
    assert bot.total_commission_paid_rub == 900.0

@pytest.mark.asyncio
async def test_unprofitable_deal(monkeypatch):
    # monkeypatch - встроенная фикстура pytest

    # тест написан по структуре arrange-act-assert

    # Arrange
    trade = Trade(profit_usdt=-100.0, commission_paid=False, freqtrade_trade_id=1)
    user = User(commission_rate=0.1, service_balance=5000.0)
    bot = Bot(
        total_profit=0.0,
        total_commission_paid_usdt=0.0,
        total_commission_paid_rub=0.0,
    )

    # Подменяем ExchangeRateService на fake с фиксированным курсом
    monkeypatch.setattr(
        "src.services.commission_service.ExchangeRateService",
        lambda: FakeExchangeRateService(rate=90.0),
    )

    # Act
    await CommissionService.process_commission(trade, user, bot)

    # Assert
    assert bot.total_profit == -100.0
    assert trade.commission_paid is False
    assert user.service_balance == 5000.0  
    assert bot.total_commission_paid_usdt == 0.0
    assert bot.total_commission_paid_rub == 0.0

@pytest.mark.asyncio
async def test_cant_get_rate(monkeypatch):
    # monkeypatch - встроенная фикстура pytest

    # тест написан по структуре arrange-act-assert

    # Arrange
    trade = Trade(profit_usdt=50.0, commission_paid=False, freqtrade_trade_id=1)
    user = User(commission_rate=0.1, service_balance=5000.0)
    bot = Bot(
        total_profit=0.0,
        total_commission_paid_usdt=0.0,
        total_commission_paid_rub=0.0,
    )

    # Подменяем ExchangeRateService на fake с фиксированным курсом
    monkeypatch.setattr(
        "src.services.commission_service.ExchangeRateService",
        lambda: FakeExchangeRateService(rate=None),
    )

    # Act
    # Assert
    with pytest.raises(ValueError):
        await CommissionService.process_commission(trade, user, bot)


