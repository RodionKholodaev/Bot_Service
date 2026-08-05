"""
Юнит-тесты для StatsService.

Идея простая: считать статистику (P&L, просадка, winrate) вручную по 5-10 сделкам
на бумажке — долго и легко ошибиться. Вместо этого один раз считаем "правильный"
результат для конкретного набора сделок здесь, в тесте, и дальше pytest сам
сверяет код с этим ожиданием при каждом запуске. Если кто-то (в том числе вы сами
через полгода) случайно сломает формулу — тест сразу покраснеет.

Все тесты идут без реальной БД:
- _build_pnl_chart и _max_drawdown — обычные статические функции, БД им не нужна вовсе.
- get_bot_stats ходит в БД через trade_repo, поэтому туда подсовывается "fake"
  репозиторий (см. FakeTradeRepo ниже), который просто отдаёт заранее заданный
  список сделок вместо похода в Postgres/SQLite.
"""

from datetime import datetime, timezone

import pytest

from src.models.bot import Bot
from src.models.trade import Trade
from src.services.stats_service import StatsService


# ──────────────────────────────────────────────
# Вспомогательные фабрики — чтобы в каждом тесте не перечислять
# по 10 обязательных полей Trade/Bot, а указывать только то, что
# важно для конкретного теста.
# ──────────────────────────────────────────────

def make_trade(
    *,
    id: int = 1,
    profit_usdt: float | None = 0.0,
    profit_pct: float | None = 0.0,
    close_time: datetime | None = None,
) -> Trade:
    """Создаёт сделку в памяти (без записи в БД) с разумными дефолтами.

    Обязательные поля Trade (pair, open_rate, open_time и т.д.) заполнены
    заглушками — в тестах на статистику важны только profit_usdt/profit_pct/close_time.
    """
    return Trade(
        id=id,
        bot_id="bot-1",
        user_id=1,
        freqtrade_trade_id=id,
        pair="BTC/USDT",
        direction="long",
        open_rate=100.0,
        close_rate=101.0,
        amount=1.0,
        leverage=1.0,
        profit_usdt=profit_usdt,
        profit_pct=profit_pct,
        exit_reason="tp",
        open_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        close_time=close_time,
    )


def make_bot(**overrides) -> Bot:
    """Бот с дефолтами, нужными для сборки BotStats (name/pair/... не могут быть None)."""
    defaults = dict(
        id="bot-1",
        user_id=1,
        name="Test Bot",
        pair="BTC/USDT",
        leverage=1,
        direction="long",
        strategy_preset="moderate",
        status="running",
        total_profit=0.0,
    )
    defaults.update(overrides)
    return Bot(**defaults)


# ──────────────────────────────────────────────
# Fake-репозиторий сделок для тестов get_bot_stats.
#
# get_bot_stats устроен так:
#   query = await self.trade_repo.get_bot_close_trades(...)   # получить select(...)
#   query = query.order_by(...)                                # что-то доклеить к запросу
#   result = await self.trade_repo.db.execute(query)            # выполнить в БД
#   trades = result.scalars().all()                             # достать список
#
# Чтобы не поднимать настоящую БД, нужно подделать каждый из этих шагов так,
# чтобы в итоге get_bot_stats получил на руки именно тот список сделок,
# который мы сами подготовили в тесте.
# ──────────────────────────────────────────────

class _FakeQuery:
    """Заглушка вместо SQLAlchemy select(...).

    Реальный код вызывает на запросе .where(...) и .order_by(...) перед выполнением.
    Нам не нужно, чтобы они реально что-то фильтровали/сортировали — сделки
    в тесте мы и так передаём в нужном порядке, поэтому просто возвращаем себя же.
    """

    def where(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self


class _FakeScalars:
    def __init__(self, items: list[Trade]):
        self._items = items

    def all(self):
        return self._items


class _FakeResult:
    def __init__(self, items: list[Trade]):
        self._items = items

    def scalars(self):
        return _FakeScalars(self._items)


class FakeTradeRepo:
    """Fake вместо TradeRepository — вместо похода в БД отдаёт список сделок,
    заданный при создании. Список сделок нужно передавать уже в том порядке,
    в котором их бы вернула настоящая БД (по close_time по возрастанию).
    """

    def __init__(self, trades: list[Trade]):
        self._trades = trades
        # StatsService дёргает self.trade_repo.db.execute(...) — значит у fake-репозитория
        # тоже должен быть атрибут .db с методом execute(). Проще всего сделать db = сам репозиторий.
        self.db = self

    async def get_bot_close_trades(self, user_id, bot_id):
        return _FakeQuery()

    async def execute(self, query):
        return _FakeResult(self._trades)


# ──────────────────────────────────────────────
# Тесты _build_pnl_chart
# ──────────────────────────────────────────────

def test_pnl_chart_accumulates_profit_step_by_step():
    # Arrange: три закрытые сделки с известной прибылью
    trades = [
        make_trade(id=1, profit_usdt=10.0, close_time=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        make_trade(id=2, profit_usdt=-5.0, close_time=datetime(2026, 1, 2, tzinfo=timezone.utc)),
        make_trade(id=3, profit_usdt=20.0, close_time=datetime(2026, 1, 3, tzinfo=timezone.utc)),
    ]

    # Act
    chart = StatsService._build_pnl_chart(trades)

    # Assert: накопленный P&L должен идти 10 -> 5 -> 25
    assert [p.value for p in chart] == [10.0, 5.0, 25.0]
    assert len(chart) == 3


def test_pnl_chart_skips_trades_without_close_time_or_profit():
    # Arrange: вторая сделка ещё не закрыта (close_time=None) — freqtrade иногда
    # присылает такие "хвосты", их не должно быть на графике и они не должны
    # влиять на накопленную сумму следующих точек.
    trades = [
        make_trade(id=1, profit_usdt=10.0, close_time=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        make_trade(id=2, profit_usdt=100.0, close_time=None),  # не закрыта — пропускаем
        make_trade(id=3, profit_usdt=None, close_time=datetime(2026, 1, 2, tzinfo=timezone.utc)),  # нет profit — пропускаем
        make_trade(id=4, profit_usdt=5.0, close_time=datetime(2026, 1, 3, tzinfo=timezone.utc)),
    ]

    # Act
    chart = StatsService._build_pnl_chart(trades)

    # Assert: в графике только 2 точки (сделки 1 и 4), и накопление идёт без "утечки"
    # прибыли из пропущенной сделки id=2 (иначе было бы 10 -> 110, а не 10 -> 15)
    assert [p.value for p in chart] == [10.0, 15.0]


def test_pnl_chart_empty_list_returns_empty_chart():
    assert StatsService._build_pnl_chart([]) == []


# ──────────────────────────────────────────────
# Тесты _max_drawdown
#
# Формула в коде: идём по сделкам, копим cumulative P&L, запоминаем текущий
# максимум (peak) и самое большое падение от пика (max_dd). В конце
# max_dd переводится в проценты от пика.
# ──────────────────────────────────────────────

def test_max_drawdown_no_trades_returns_none():
    assert StatsService._max_drawdown([]) is None


def test_max_drawdown_only_profitable_trades_is_zero():
    # Arrange: прибыль только растёт, просадок не было вообще
    trades = [
        make_trade(id=1, profit_usdt=10.0),
        make_trade(id=2, profit_usdt=20.0),
        make_trade(id=3, profit_usdt=30.0),
    ]

    # Act / Assert: раз пик всё время обновлялся вместе с cumulative, просадки нет
    assert StatsService._max_drawdown(trades) == 0.0


def test_max_drawdown_calculates_percent_from_peak():
    # Arrange: сначала растём до пика 150, потом проседаем до 50, потом немного отрастаем.
    # Порядок такой же, как рассчитан вручную в комментарии ниже — если формулу в коде
    # поменяют, этот тест первым покажет, что результат изменился.
    trades = [
        make_trade(id=1, profit_usdt=100.0),   # cumulative=100, peak=100, dd=0
        make_trade(id=2, profit_usdt=50.0),    # cumulative=150, peak=150, dd=0
        make_trade(id=3, profit_usdt=-80.0),   # cumulative=70,  peak=150, dd=-80
        make_trade(id=4, profit_usdt=-20.0),   # cumulative=50,  peak=150, dd=-100  <- самая глубокая просадка
        make_trade(id=5, profit_usdt=10.0),    # cumulative=60,  peak=150, dd=-90
    ]

    # Act
    result = StatsService._max_drawdown(trades)

    # Assert: max_dd = -100, peak = 150 => -100/150*100 = -66.67%
    assert result == -66.67


def test_max_drawdown_never_profitable_returns_none():
    # Arrange: cumulative никогда не поднимался выше 0 — пика по факту не было.
    # Это осознанное поведение текущего кода (peak == 0 -> None), а не баг,
    # но оно неочевидно: у бота реально была просадка, а StatsService вернёт None.
    trades = [
        make_trade(id=1, profit_usdt=-10.0),
        make_trade(id=2, profit_usdt=-20.0),
    ]

    assert StatsService._max_drawdown(trades) is None


# ──────────────────────────────────────────────
# Тесты get_bot_stats: winrate, победы/поражения, средняя прибыль в %
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_bot_stats_winrate_and_counts():
    # Arrange: 2 победы, 1 поражение, 1 сделка "в ноль"
    trades = [
        make_trade(id=1, profit_usdt=100.0, profit_pct=5.0, close_time=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        make_trade(id=2, profit_usdt=-50.0, profit_pct=-2.0, close_time=datetime(2026, 1, 2, tzinfo=timezone.utc)),
        make_trade(id=3, profit_usdt=0.0, profit_pct=0.0, close_time=datetime(2026, 1, 3, tzinfo=timezone.utc)),
        make_trade(id=4, profit_usdt=30.0, profit_pct=3.0, close_time=datetime(2026, 1, 4, tzinfo=timezone.utc)),
    ]
    bot = make_bot()
    service = StatsService(bot_repo=None, trade_repo=FakeTradeRepo(trades))

    # Act
    stats = await service.get_bot_stats(bot)

    # Assert
    assert stats.trades_total == 4
    # сделка с profit_usdt=0.0 (id=3) в коде считается поражением (profit <= 0),
    # поэтому побед 2 (id=1, id=4), а не 3
    assert stats.trades_win == 2
    assert stats.trades_loss == 2
    assert stats.winrate == 50.0
    # средний profit_pct по всем 4 сделкам: (5 - 2 + 0 + 3) / 4 = 1.5
    assert stats.avg_profit_pct == 1.5


@pytest.mark.asyncio
async def test_get_bot_stats_zero_profit_trade_counts_as_loss():
    # Отдельный тест на конкретное неочевидное правило: сделка, закрытая
    # ровно "в ноль" (profit_usdt == 0), в статистике идёт в поражения,
    # а не в отдельную категорию "без результата". Если бы кто-то по интуиции
    # считал такие сделки нейтральными, здесь бы разошлось с ожиданием.
    trades = [
        make_trade(id=1, profit_usdt=0.0, close_time=datetime(2026, 1, 1, tzinfo=timezone.utc)),
    ]
    bot = make_bot()
    service = StatsService(bot_repo=None, trade_repo=FakeTradeRepo(trades))

    stats = await service.get_bot_stats(bot)

    assert stats.trades_win == 0
    assert stats.trades_loss == 1
    assert stats.winrate == 0.0


@pytest.mark.asyncio
async def test_get_bot_stats_no_trades_returns_zero_stats_without_crashing():
    # Arrange: у бота вообще ещё нет закрытых сделок (только что создан)
    bot = make_bot()
    service = StatsService(bot_repo=None, trade_repo=FakeTradeRepo([]))

    # Act
    stats = await service.get_bot_stats(bot)

    # Assert: важно, что это не падает с делением на ноль, а аккуратно возвращает нули
    assert stats.trades_total == 0
    assert stats.winrate == 0.0
    assert stats.avg_profit_pct is None
    assert stats.max_drawdown_pct is None
    assert stats.pnl_chart == []
