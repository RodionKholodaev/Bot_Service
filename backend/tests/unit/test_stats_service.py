"""
Юнит-тесты для StatsService.

Идея простая: считать статистику (P&L, просадка, winrate) вручную по 5-10 сделкам
на бумажке — долго и легко ошибиться. Вместо этого один раз считаем "правильный"
результат для конкретного набора сделок здесь, в тесте, и дальше pytest сам
сверяет код с этим ожиданием при каждом запуске. Если кто-то (в том числе вы сами
через полгода) случайно сломает формулу — тест сразу покраснеет.

Все тесты идут без реальной БД: репозитории подменяются fake-объектами (см. ниже),
которые отдают заранее заданные списки вместо похода в Postgres/SQLite.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.models.bot import Bot
from src.models.trade import Trade
from src.models.user import User
from src.services.stats_service import StatsService

# ──────────────────────────────────────────────
# Вспомогательные фабрики — чтобы в каждом тесте не перечислять
# по 10 обязательных полей Trade/Bot, а указывать только то, что
# важно для конкретного теста.
# ──────────────────────────────────────────────


def make_trade(
    *,
    id: int = 1,
    bot_id: str = "bot-1",
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
        bot_id=bot_id,
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
        open_time=datetime(2026, 1, 1, tzinfo=UTC),
        close_time=close_time,
    )


def make_bot(**overrides) -> Bot:
    """Бот с дефолтами, нужными для сборки BotStats (name/pair/... не могут быть None).

    is_active, stake_amount и dry_run задаются явно: в БД у них есть default, но у
    объекта, созданного в памяти без flush, они остались бы None — активный бот выглядел
    бы архивированным, просадку было бы не от чего считать, а BotSummary.dry_run (bool)
    вообще не прошёл бы валидацию.
    """
    defaults = {
        "id": "bot-1",
        "user_id": 1,
        "name": "Test Bot",
        "pair": "BTC/USDT",
        "leverage": 1,
        "direction": "long",
        "strategy_preset": "moderate",
        "status": "running",
        "total_profit": 0.0,
        "stake_amount": 1000.0,
        "is_active": True,
        "dry_run": False,
    }
    defaults.update(overrides)
    return Bot(**defaults)


# ──────────────────────────────────────────────
# Fake-репозитории.
#
# StatsService теперь получает от репозитория готовый список сделок
# (repo.get_closed_trades(...) -> list[Trade]), а не Select, который сервис сам
# доводил бы до ума. Поэтому и fake простой: отдать заданный список и запомнить,
# с какими аргументами его позвали.
# ──────────────────────────────────────────────


class FakeTradeRepo:
    def __init__(self, trades: list[Trade]):
        self._trades = trades
        # чем позвали — по этому проверяем, что сервис правильно прокидывает период
        self.calls: list[dict] = []

    async def get_closed_trades(self, user_id, *, bot_id=None, since=None, dry_run=None) -> list[Trade]:
        self.calls.append({"user_id": user_id, "bot_id": bot_id, "since": since, "dry_run": dry_run})
        # Настоящий репозиторий фильтрует в SQL. Здесь повторяем только фильтр по боту:
        # он нужен, чтобы тесты могли смешивать сделки нескольких ботов в одном наборе.
        # Фильтр по since и по dry_run не повторяем намеренно — иначе тест проверял бы
        # сам fake, а не то, что сервис посчитал границу периода и передал её вниз
        # (dry_run настоящий репозиторий вообще фильтрует join-ом с bots).
        if bot_id is not None:
            return [t for t in self._trades if t.bot_id == bot_id]
        return list(self._trades)


class FakeBotRepo:
    def __init__(self, bots: list[Bot]):
        self._bots = bots

    async def get_user_active_bots(self, user_id, *, dry_run=None) -> list[Bot]:
        # фильтр по dry_run повторяем: настоящий репозиторий делает ровно это одним
        # .where(), и без него было бы не видно, что сервис вообще его прокинул
        return [b for b in self._bots if b.is_active and (dry_run is None or b.dry_run is dry_run)]

    async def get_user_bots(self, user_id) -> list[Bot]:
        return list(self._bots)


def make_service(trades: list[Trade] | None = None, bots: list[Bot] | None = None) -> StatsService:
    return StatsService(
        bot_repo=FakeBotRepo(bots or []),  # type: ignore[arg-type]
        trade_repo=FakeTradeRepo(trades or []),  # type: ignore[arg-type]
    )


# ──────────────────────────────────────────────
# Тесты _build_pnl_chart
# ──────────────────────────────────────────────


def test_pnl_chart_accumulates_profit_step_by_step():
    # Arrange: три закрытые сделки с известной прибылью
    trades = [
        make_trade(id=1, profit_usdt=10.0, close_time=datetime(2026, 1, 1, tzinfo=UTC)),
        make_trade(id=2, profit_usdt=-5.0, close_time=datetime(2026, 1, 2, tzinfo=UTC)),
        make_trade(id=3, profit_usdt=20.0, close_time=datetime(2026, 1, 3, tzinfo=UTC)),
    ]

    # Act
    chart = StatsService._build_pnl_chart(trades)

    # Assert: накопленный P&L должен идти 10 -> 5 -> 25
    assert [p.value for p in chart] == [10.0, 5.0, 25.0]
    assert len(chart) == 3


def test_pnl_chart_point_keeps_raw_close_time():
    # Метка времени уезжает на фронт как datetime, а не как заранее склеенная строка
    # "%d.%m %H:%M": в такой строке нет года (за период "all" метки повторяются между
    # годами) и нет часового пояса пользователя.
    close_time = datetime(2026, 1, 1, 12, 30, tzinfo=UTC)
    trades = [make_trade(id=1, profit_usdt=10.0, close_time=close_time)]

    chart = StatsService._build_pnl_chart(trades)

    assert chart[0].ts == close_time


def test_pnl_chart_skips_trades_without_close_time_or_profit():
    # Arrange: вторая сделка ещё не закрыта (close_time=None) — freqtrade иногда
    # присылает такие "хвосты", их не должно быть на графике и они не должны
    # влиять на накопленную сумму следующих точек.
    trades = [
        make_trade(id=1, profit_usdt=10.0, close_time=datetime(2026, 1, 1, tzinfo=UTC)),
        make_trade(id=2, profit_usdt=100.0, close_time=None),  # не закрыта — пропускаем
        make_trade(id=3, profit_usdt=None, close_time=datetime(2026, 1, 2, tzinfo=UTC)),  # нет profit — пропускаем
        make_trade(id=4, profit_usdt=5.0, close_time=datetime(2026, 1, 3, tzinfo=UTC)),
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
# Формула: кривая капитала начинается со вложенной суммы (stake_amount), к ней
# прибавляется P&L каждой сделки; ищем самое глубокое падение от достигнутого пика
# и переводим его в проценты от этого пика.
# ──────────────────────────────────────────────


def test_max_drawdown_no_trades_returns_none():
    assert StatsService._max_drawdown([], 1000.0) is None


def test_max_drawdown_without_base_capital_returns_none():
    # Не от чего считать процент: у бота неизвестен вложенный капитал.
    trades = [make_trade(id=1, profit_usdt=-10.0)]

    assert StatsService._max_drawdown(trades, None) is None
    assert StatsService._max_drawdown(trades, 0.0) is None


def test_max_drawdown_only_profitable_trades_is_zero():
    # Arrange: капитал только растёт, просадок не было вообще
    trades = [
        make_trade(id=1, profit_usdt=10.0),
        make_trade(id=2, profit_usdt=20.0),
        make_trade(id=3, profit_usdt=30.0),
    ]

    # Act / Assert: раз пик всё время обновлялся вместе с кривой, просадки нет
    assert StatsService._max_drawdown(trades, 1000.0) == 0.0


def test_max_drawdown_calculates_percent_from_peak_equity():
    # Arrange: вложено 1000, кривая идёт 1100 -> 1150 -> 1070 -> 1050 -> 1060.
    # Пик 1150, самая нижняя точка после него 1050.
    trades = [
        make_trade(id=1, profit_usdt=100.0),
        make_trade(id=2, profit_usdt=50.0),
        make_trade(id=3, profit_usdt=-80.0),
        make_trade(id=4, profit_usdt=-20.0),  # <- дно
        make_trade(id=5, profit_usdt=10.0),
    ]

    # Act
    result = StatsService._max_drawdown(trades, 1000.0)

    # Assert: (1050 - 1150) / 1150 * 100 = -8.7%
    assert result == -8.7


def test_max_drawdown_never_profitable_bot_still_has_drawdown():
    # Раньше у бота, который ни разу не выходил в плюс, пик кумулятивной прибыли
    # оставался нулём и функция возвращала None — фронт показывал "просадки нет"
    # ровно там, где она максимальная. Теперь считается от вложенного капитала.
    trades = [
        make_trade(id=1, profit_usdt=-10.0),
        make_trade(id=2, profit_usdt=-20.0),
    ]

    # (970 - 1000) / 1000 * 100 = -3.0%
    assert StatsService._max_drawdown(trades, 1000.0) == -3.0


# ──────────────────────────────────────────────
# Тесты get_bot_stats: winrate, победы/поражения, средняя прибыль в %
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_bot_stats_winrate_and_counts():
    # Arrange: 2 победы, 1 поражение, 1 сделка "в ноль"
    trades = [
        make_trade(id=1, profit_usdt=100.0, profit_pct=5.0, close_time=datetime(2026, 1, 1, tzinfo=UTC)),
        make_trade(id=2, profit_usdt=-50.0, profit_pct=-2.0, close_time=datetime(2026, 1, 2, tzinfo=UTC)),
        make_trade(id=3, profit_usdt=0.0, profit_pct=0.0, close_time=datetime(2026, 1, 3, tzinfo=UTC)),
        make_trade(id=4, profit_usdt=30.0, profit_pct=3.0, close_time=datetime(2026, 1, 4, tzinfo=UTC)),
    ]
    bot = make_bot()
    service = make_service(trades)

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
async def test_get_bot_stats_profit_comes_from_trades_not_from_bot_counter():
    # Bot.total_profit — счётчик за всё время, он не знает про выбранный период.
    # Раньше именно он уезжал в ответ, и карточка "P&L за период" на фронте
    # расходилась с графиком под ней.
    trades = [
        make_trade(id=1, profit_usdt=10.0, close_time=datetime(2026, 1, 1, tzinfo=UTC)),
        make_trade(id=2, profit_usdt=-4.0, close_time=datetime(2026, 1, 2, tzinfo=UTC)),
    ]
    bot = make_bot(total_profit=999.0)
    service = make_service(trades)

    stats = await service.get_bot_stats(bot)

    assert stats.profit == 6.0
    # и последняя точка графика сходится с этим числом
    assert stats.pnl_chart[-1].value == 6.0


@pytest.mark.asyncio
async def test_get_bot_stats_passes_period_boundary_to_repository():
    # Отсечка по периоду должна уходить в SQL, а не считаться где-то в питоне
    bot = make_bot()
    repo = FakeTradeRepo([])
    service = StatsService(bot_repo=FakeBotRepo([]), trade_repo=repo)  # type: ignore[arg-type]

    await service.get_bot_stats(bot, period_days=7)

    call = repo.calls[0]
    assert call["bot_id"] == bot.id
    assert call["since"] is not None
    # примерно неделю назад (с запасом на время выполнения теста)
    expected = datetime.now(UTC) - timedelta(days=7)
    assert abs((call["since"] - expected).total_seconds()) < 60


@pytest.mark.asyncio
async def test_get_bot_stats_all_period_has_no_boundary():
    bot = make_bot()
    repo = FakeTradeRepo([])
    service = StatsService(bot_repo=FakeBotRepo([]), trade_repo=repo)  # type: ignore[arg-type]

    await service.get_bot_stats(bot, period_days=None)

    assert repo.calls[0]["since"] is None


@pytest.mark.asyncio
async def test_get_bot_stats_recent_trades_are_newest_first():
    # Репозиторий отдаёт сделки по возрастанию close_time, в таблице нужен обратный порядок
    trades = [make_trade(id=i, profit_usdt=1.0, close_time=datetime(2026, 1, i, tzinfo=UTC)) for i in range(1, 6)]
    service = make_service(trades)

    stats = await service.get_bot_stats(make_bot(), recent_limit=3)

    assert [t.id for t in stats.recent_trades] == [5, 4, 3]


@pytest.mark.asyncio
async def test_get_bot_stats_zero_profit_trade_counts_as_loss():
    # Отдельный тест на конкретное неочевидное правило: сделка, закрытая
    # ровно "в ноль" (profit_usdt == 0), в статистике идёт в поражения,
    # а не в отдельную категорию "без результата". Если бы кто-то по интуиции
    # считал такие сделки нейтральными, здесь бы разошлось с ожиданием.
    trades = [
        make_trade(id=1, profit_usdt=0.0, close_time=datetime(2026, 1, 1, tzinfo=UTC)),
    ]
    service = make_service(trades)

    stats = await service.get_bot_stats(make_bot())

    assert stats.trades_win == 0
    assert stats.trades_loss == 1
    assert stats.winrate == 0.0


@pytest.mark.asyncio
async def test_get_bot_stats_no_trades_returns_zero_stats_without_crashing():
    # Arrange: у бота вообще ещё нет закрытых сделок (только что создан)
    service = make_service([])

    # Act
    stats = await service.get_bot_stats(make_bot())

    # Assert: важно, что это не падает с делением на ноль, а аккуратно возвращает нули
    assert stats.trades_total == 0
    assert stats.profit == 0.0
    assert stats.winrate == 0.0
    assert stats.avg_profit_pct is None
    assert stats.max_drawdown_pct is None
    assert stats.pnl_chart == []


# ──────────────────────────────────────────────
# Тесты get_portfolio_stats
# ──────────────────────────────────────────────


def make_user() -> User:
    return User(id=1, service_balance=0.0, commission_rate=0.1)


@pytest.mark.asyncio
async def test_portfolio_profit_matches_its_own_chart_and_winrate():
    # Главное свойство портфеля: прибыль, winrate и график считаются по одному и тому же
    # набору сделок. Раньше прибыль брали из Bot.total_profit (за всё время), и на любом
    # периоде кроме "all" карточка расходилась с графиком.
    trades = [
        make_trade(id=1, profit_usdt=30.0, close_time=datetime(2026, 1, 1, tzinfo=UTC)),
        make_trade(id=2, profit_usdt=-10.0, close_time=datetime(2026, 1, 2, tzinfo=UTC)),
    ]
    bots = [make_bot(total_profit=999.0)]
    service = make_service(trades, bots)

    stats = await service.get_portfolio_stats(make_user(), period_days=7)

    assert stats.profit == 20.0
    assert stats.pnl_chart[-1].value == 20.0
    assert stats.trades_total == 2
    assert stats.trades_win == 1
    assert stats.trades_loss == 1
    assert stats.winrate == 50.0


@pytest.mark.asyncio
async def test_portfolio_splits_trades_between_bots_for_sidebar():
    # Сводка по каждому боту собирается из той же единственной выборки сделок,
    # без отдельного запроса на каждого бота.
    trades = [
        make_trade(id=1, bot_id="bot-1", profit_usdt=10.0, close_time=datetime(2026, 1, 1, tzinfo=UTC)),
        make_trade(id=2, bot_id="bot-2", profit_usdt=-5.0, close_time=datetime(2026, 1, 2, tzinfo=UTC)),
        make_trade(id=3, bot_id="bot-1", profit_usdt=4.0, close_time=datetime(2026, 1, 3, tzinfo=UTC)),
    ]
    bots = [make_bot(id="bot-1"), make_bot(id="bot-2", status="stopped")]
    service = make_service(trades, bots)

    stats = await service.get_portfolio_stats(make_user())

    by_id = {b.bot_id: b for b in stats.bots}
    assert by_id["bot-1"].profit == 14.0
    assert by_id["bot-1"].trades_total == 2
    assert by_id["bot-1"].winrate == 100.0
    assert by_id["bot-2"].profit == -5.0
    assert by_id["bot-2"].winrate == 0.0
    # бот без сделок за период не должен пропадать из сайдбара
    assert stats.bots_running == 1
    assert stats.bots_stopped == 1


@pytest.mark.asyncio
async def test_portfolio_keeps_trades_of_archived_bots_but_hides_them_from_sidebar():
    # Удаление бота у нас мягкое: строка остаётся, сделки остаются. Заработанное им
    # должно остаться в общей истории, иначе удаление бота молча переписывает
    # статистику пользователя за прошлые периоды.
    trades = [
        make_trade(id=1, bot_id="bot-1", profit_usdt=10.0, close_time=datetime(2026, 1, 1, tzinfo=UTC)),
        make_trade(id=2, bot_id="bot-archived", profit_usdt=25.0, close_time=datetime(2026, 1, 2, tzinfo=UTC)),
    ]
    bots = [make_bot(id="bot-1"), make_bot(id="bot-archived", is_active=False)]
    service = make_service(trades, bots)

    stats = await service.get_portfolio_stats(make_user())

    assert stats.profit == 35.0
    assert stats.trades_total == 2
    assert [b.bot_id for b in stats.bots] == ["bot-1"]


@pytest.mark.asyncio
async def test_portfolio_drawdown_uses_total_invested_capital():
    trades = [
        make_trade(id=1, profit_usdt=100.0, close_time=datetime(2026, 1, 1, tzinfo=UTC)),
        make_trade(id=2, profit_usdt=-200.0, close_time=datetime(2026, 1, 2, tzinfo=UTC)),
    ]
    # два бота по 1000 => база 2000, кривая 2000 -> 2100 -> 1900
    bots = [make_bot(id="bot-1"), make_bot(id="bot-2")]
    service = make_service(trades, bots)

    stats = await service.get_portfolio_stats(make_user())

    # (1900 - 2100) / 2100 * 100 = -9.52%
    assert stats.max_drawdown_pct == -9.52


@pytest.mark.asyncio
async def test_portfolio_bot_type_filter_reaches_both_repositories():
    # Фильтр «боевые / dry-run / все» должен уходить одинаковым значением и в список
    # ботов, и в выборку сделок. Если прокинуть его только в одно место, график
    # посчитается по одному набору ботов, а сайдбар и просадка — по другому.
    bots = [make_bot(id="bot-real", dry_run=False), make_bot(id="bot-dry", dry_run=True)]
    trade_repo = FakeTradeRepo([])
    service = StatsService(bot_repo=FakeBotRepo(bots), trade_repo=trade_repo)  # type: ignore[arg-type]

    stats = await service.get_portfolio_stats(make_user(), dry_run=True)

    assert trade_repo.calls[0]["dry_run"] is True
    assert [b.bot_id for b in stats.bots] == ["bot-dry"]


@pytest.mark.asyncio
async def test_portfolio_without_bot_type_filter_keeps_both_kinds():
    bots = [make_bot(id="bot-real", dry_run=False), make_bot(id="bot-dry", dry_run=True)]
    trade_repo = FakeTradeRepo([])
    service = StatsService(bot_repo=FakeBotRepo(bots), trade_repo=trade_repo)  # type: ignore[arg-type]

    stats = await service.get_portfolio_stats(make_user())

    assert trade_repo.calls[0]["dry_run"] is None
    assert {b.bot_id for b in stats.bots} == {"bot-real", "bot-dry"}


@pytest.mark.asyncio
async def test_portfolio_drawdown_counts_only_capital_of_filtered_bots():
    # Просадка считается от вложенного капитала, и при фильтре по типу бота в базу
    # должен попадать депозит только отфильтрованных ботов: иначе dry-run бот на 1000
    # размывал бы просадку боевого.
    trades = [
        make_trade(id=1, profit_usdt=100.0, close_time=datetime(2026, 1, 1, tzinfo=UTC)),
        make_trade(id=2, profit_usdt=-200.0, close_time=datetime(2026, 1, 2, tzinfo=UTC)),
    ]
    bots = [
        make_bot(id="bot-real", dry_run=False, stake_amount=1000.0),
        make_bot(id="bot-dry", dry_run=True, stake_amount=1000.0),
    ]
    service = make_service(trades, bots)

    stats = await service.get_portfolio_stats(make_user(), dry_run=False)

    # база 1000 (только боевой бот), кривая 1000 -> 1100 -> 900: (900-1100)/1100 = -18.18%
    assert stats.max_drawdown_pct == -18.18


@pytest.mark.asyncio
async def test_portfolio_without_bots_and_trades_does_not_crash():
    service = make_service([], [])

    stats = await service.get_portfolio_stats(make_user())

    assert stats.profit == 0.0
    assert stats.winrate == 0.0
    assert stats.max_drawdown_pct is None
    assert stats.bots == []


# ──────────────────────────────────────────────
# Тесты get_home_stats
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_home_total_profit_includes_archived_bots():
    # На главной "общий профит" — за всё время, поэтому вклад удалённых ботов
    # из него исчезать не должен. А вот в счётчик ботов они уже не идут.
    bots = [
        make_bot(id="bot-1", total_profit=100.0),
        make_bot(id="bot-archived", total_profit=50.0, is_active=False),
    ]
    service = make_service([], bots)
    user = make_user()
    user.service_balance = 1234.567

    stats = await service.get_home_stats(user)

    assert stats.total_profit == 150.0
    assert stats.bots_total == 1
    assert stats.bots_running == 1
    assert stats.service_balance == 1234.57


@pytest.mark.asyncio
async def test_home_funds_under_management_counts_only_working_bots():
    bots = [
        make_bot(id="bot-1", status="running", stake_amount=500.0),
        make_bot(id="bot-2", status="starting", stake_amount=300.0),
        make_bot(id="bot-3", status="stopped", stake_amount=700.0),
        make_bot(id="bot-4", status="running", stake_amount=100.0, is_active=False),
    ]
    service = make_service([], bots)

    stats = await service.get_home_stats(make_user())

    assert stats.funds_under_management == 800.0


@pytest.mark.asyncio
async def test_home_weekly_profit_asks_repository_for_last_seven_days():
    trades = [
        make_trade(id=1, profit_usdt=5.0, close_time=datetime(2026, 1, 1, tzinfo=UTC)),
        make_trade(id=2, profit_usdt=2.5, close_time=datetime(2026, 1, 2, tzinfo=UTC)),
    ]
    repo = FakeTradeRepo(trades)
    service = StatsService(bot_repo=FakeBotRepo([]), trade_repo=repo)  # type: ignore[arg-type]

    stats = await service.get_home_stats(make_user())

    assert stats.weekly_profit == 7.5
    expected = datetime.now(UTC) - timedelta(days=7)
    assert abs((repo.calls[0]["since"] - expected).total_seconds()) < 60
