"""
Тест TradeRepository.get_open_trades против настоящей (тестовой) БД.

Ручка /bots/{id}/open-trades нужна ровно для одного: предупредить, что удаление
бота с открытой позицией оставит её на бирже без всякой связи с сервисом. Цена
ошибки здесь — либо предупреждения не будет там, где оно нужно, либо оно будет
пугать на пустом месте.

Весь смысл метода — в SQL-фильтре, и фейковым репозиторием он не проверяется:
фейк вернул бы свой список при любом запросе. Поэтому тест интеграционный —
выполняется настоящий запрос к тестовой SQLite.

Отдельно закреплено, что открытость определяется по close_time, а не по
close_rate: у части закрытых сделок close_rate так и остался NULL (freqtrade не
досчитал результат к моменту опроса), и по нему они выглядели бы открытыми.
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.models.bot import Bot
from src.models.trade import Trade
from src.models.user import User
from src.repositories.trade_repository import TradeRepository


async def make_user(db_session, *, email: str = "owner@test.com") -> User:
    user = User(username="rodion", email=email, password_hash="hash")
    db_session.add(user)
    await db_session.flush()
    return user


async def make_bot(db_session, *, owner: User, bot_id: str = "bot-1") -> Bot:
    bot = Bot(
        id=bot_id,
        user_id=owner.id,
        name="Бот",
        pair="XRP/USDT:USDT",
        leverage=10,
        direction="long",
        strategy_preset="moderate",
        entry_filters_long=[],
        entry_filters_short=[],
        take_profit={"0": 0.15},
        stop_loss=-0.1,
        dry_run=False,
        status="stopped",
        container_name=f"container_{bot_id}",
        api_port=9000 + len(bot_id),
        api_username="freqtrader",
        api_password="pass",
        stake_amount=100.0,
        tradable_balance_ratio=0.2,
        is_active=True,
    )
    db_session.add(bot)
    await db_session.flush()
    return bot


async def make_trade(
    db_session,
    *,
    bot: Bot,
    owner: User,
    freqtrade_trade_id: int,
    close_time: datetime | None,
    close_rate: float | None = None,
    open_time: datetime | None = None,
) -> Trade:
    trade = Trade(
        bot_id=bot.id,
        user_id=owner.id,
        freqtrade_trade_id=freqtrade_trade_id,
        pair="XRP/USDT:USDT",
        direction="long",
        open_rate=2.0,
        close_rate=close_rate,
        amount=50.0,
        leverage=10,
        open_time=open_time or datetime.now(UTC),
        close_time=close_time,
    )
    db_session.add(trade)
    await db_session.flush()
    return trade


@pytest.mark.asyncio
async def test_open_trade_is_returned(db_session):
    owner = await make_user(db_session)
    bot = await make_bot(db_session, owner=owner)
    trade = await make_trade(db_session, bot=bot, owner=owner, freqtrade_trade_id=1, close_time=None)

    open_trades = await TradeRepository(db_session).get_open_trades(bot.id)

    assert [t.id for t in open_trades] == [trade.id]


@pytest.mark.asyncio
async def test_closed_trade_is_not_returned(db_session):
    owner = await make_user(db_session)
    bot = await make_bot(db_session, owner=owner)
    await make_trade(
        db_session,
        bot=bot,
        owner=owner,
        freqtrade_trade_id=1,
        close_time=datetime.now(UTC),
        close_rate=2.5,
    )

    open_trades = await TradeRepository(db_session).get_open_trades(bot.id)

    assert open_trades == []


@pytest.mark.asyncio
async def test_closed_trade_without_close_rate_is_not_returned(db_session):
    owner = await make_user(db_session)
    bot = await make_bot(db_session, owner=owner)
    # Сделка закрыта, но результат freqtrade не досчитал — в боевой БД таких семь.
    # По close_rate она выглядела бы открытой, и пользователя пугали бы позицией,
    # которой на бирже давно нет.
    await make_trade(
        db_session,
        bot=bot,
        owner=owner,
        freqtrade_trade_id=1,
        close_time=datetime.now(UTC),
        close_rate=None,
    )

    open_trades = await TradeRepository(db_session).get_open_trades(bot.id)

    assert open_trades == []


@pytest.mark.asyncio
async def test_open_trade_of_another_bot_is_not_returned(db_session):
    owner = await make_user(db_session)
    bot = await make_bot(db_session, owner=owner, bot_id="bot-1")
    other_bot = await make_bot(db_session, owner=owner, bot_id="bot-2")
    await make_trade(db_session, bot=other_bot, owner=owner, freqtrade_trade_id=1, close_time=None)

    open_trades = await TradeRepository(db_session).get_open_trades(bot.id)

    # предупреждение при удалении обязано считать только сделки удаляемого бота
    assert open_trades == []


@pytest.mark.asyncio
async def test_open_trades_are_ordered_by_open_time(db_session):
    owner = await make_user(db_session)
    bot = await make_bot(db_session, owner=owner)
    now = datetime.now(UTC)
    # добавляем в обратном порядке — на неотсортированном запросе они так и вернутся
    later = await make_trade(db_session, bot=bot, owner=owner, freqtrade_trade_id=2, close_time=None, open_time=now)
    earlier = await make_trade(
        db_session, bot=bot, owner=owner, freqtrade_trade_id=1, close_time=None, open_time=now - timedelta(hours=1)
    )

    open_trades = await TradeRepository(db_session).get_open_trades(bot.id)

    assert [t.id for t in open_trades] == [earlier.id, later.id]
