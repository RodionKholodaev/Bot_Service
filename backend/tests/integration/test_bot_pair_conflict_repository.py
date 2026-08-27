"""
Тест BotRepository.get_live_bot_on_pair против настоящей (тестовой) БД.

Метод отвечает на один вопрос: занята ли уже эта торговая пара на этом биржевом
ключе. Цена ошибки — два бота на одной паре с одним ключом: биржа нетит их в одну
позицию, вход второго увеличивает позицию первого, а стоп первого закрывает её
целиком, вместе с чужой частью.

Весь смысл метода — в SQL-фильтре, и фейковым репозиторием он не проверяется:
фейк вернул бы своего бота при любом запросе. Поэтому тест интеграционный —
выполняется настоящий запрос к тестовой SQLite.
"""

import pytest

from src.models.bot import Bot
from src.models.user import User
from src.repositories.bot_repository import BotRepository

PAIR = "SOL/USDT:USDT"


async def make_user(db_session, *, email: str = "owner@test.com") -> User:
    user = User(username="rodion", email=email, password_hash="hash")
    db_session.add(user)
    await db_session.flush()
    return user


async def make_bot(
    db_session,
    *,
    owner: User,
    bot_id: str = "bot-1",
    pair: str = PAIR,
    api_key_id: int | None = 10,
    dry_run: bool = False,
    status: str = "running",
    is_active: bool = True,
) -> Bot:
    """Боевой работающий бот на паре SOL — то есть ровно тот, с кем нельзя пересекаться.

    api_key_id заполнен числом без строки в exchange_api_keys: внешние ключи в SQLite
    не включены (см. CLAUDE.md), а запросу нужен только сам идентификатор.
    """
    bot = Bot(
        id=bot_id,
        user_id=owner.id,
        name=f"Бот {bot_id}",
        pair=pair,
        leverage=10,
        direction="long",
        strategy_preset="moderate",
        entry_filters_long=[],
        entry_filters_short=[],
        take_profit={"0": 0.15},
        stop_loss=-0.1,
        dry_run=dry_run,
        status=status,
        container_name=f"container_{bot_id}",
        api_port=9000 + len(bot_id),
        api_username="freqtrader",
        api_password="pass",
        api_key_id=api_key_id,
        stake_amount=100.0,
        tradable_balance_ratio=0.2,
        is_active=is_active,
    )
    db_session.add(bot)
    await db_session.flush()
    return bot


@pytest.mark.asyncio
async def test_live_bot_on_same_key_and_pair_is_found(db_session):
    # Arrange
    owner = await make_user(db_session)
    rival = await make_bot(db_session, owner=owner)

    # Act
    found = await BotRepository(db_session).get_live_bot_on_pair(10, PAIR)

    # Assert
    assert found is not None and found.id == rival.id


@pytest.mark.asyncio
async def test_bot_on_another_pair_is_not_found(db_session):
    # Arrange
    owner = await make_user(db_session)
    await make_bot(db_session, owner=owner, pair="XRP/USDT:USDT")

    # Act
    found = await BotRepository(db_session).get_live_bot_on_pair(10, PAIR)

    # Assert: разные пары — разные позиции на бирже, мешать друг другу нечем
    assert found is None


@pytest.mark.asyncio
async def test_bot_on_another_api_key_is_not_found(db_session):
    # Arrange
    owner = await make_user(db_session)
    await make_bot(db_session, owner=owner, api_key_id=11)

    # Act
    found = await BotRepository(db_session).get_live_bot_on_pair(10, PAIR)

    # Assert: другой ключ — другой счёт на бирже, позиция тоже другая
    assert found is None


@pytest.mark.asyncio
async def test_pair_is_matched_case_insensitively(db_session):
    # Arrange
    # Пара приходит строкой из тела запроса, и "sol/usdt:usdt" — та же позиция на
    # бирже. Без func.upper это был бы обход проверки одной сменой регистра.
    owner = await make_user(db_session)
    rival = await make_bot(db_session, owner=owner, pair=PAIR)

    # Act
    found = await BotRepository(db_session).get_live_bot_on_pair(10, "sol/usdt:usdt")

    # Assert
    assert found is not None and found.id == rival.id


@pytest.mark.asyncio
async def test_dry_run_bot_is_not_found(db_session):
    # Arrange
    # Симуляция реальных ордеров не ставит — позицию на бирже она не трогает.
    owner = await make_user(db_session)
    await make_bot(db_session, owner=owner, dry_run=True)

    # Act
    found = await BotRepository(db_session).get_live_bot_on_pair(10, PAIR)

    # Assert
    assert found is None


@pytest.mark.asyncio
async def test_archived_bot_is_not_found(db_session):
    # Arrange
    # Удалённый бот остаётся в таблице ради истории сделок (мягкое удаление), но
    # контейнера у него нет — блокировать пару навсегда он не должен.
    owner = await make_user(db_session)
    await make_bot(db_session, owner=owner, is_active=False)

    # Act
    found = await BotRepository(db_session).get_live_bot_on_pair(10, PAIR)

    # Assert
    assert found is None


@pytest.mark.asyncio
async def test_statuses_filter_skips_bot_that_is_not_trading(db_session):
    # Arrange
    # Так спрашивает start_bot: ему важны только реально торгующие соседи.
    owner = await make_user(db_session)
    await make_bot(db_session, owner=owner, status="stopped")
    repo = BotRepository(db_session)

    # Act
    trading = await repo.get_live_bot_on_pair(10, PAIR, statuses=("starting", "running"))
    any_status = await repo.get_live_bot_on_pair(10, PAIR)

    # Assert: тот же бот виден без фильтра статусов (так спрашивает create_bot) и
    # невидим с ним — значит фильтр работает, а не просто ничего не находит
    assert trading is None
    assert any_status is not None


@pytest.mark.asyncio
async def test_bot_does_not_conflict_with_itself(db_session):
    # Arrange
    # create_bot записывает бота в БД, и сразу за ним router зовёт start_bot —
    # без exclude_bot_id бот нашёл бы сам себя и не запустился бы никогда.
    owner = await make_user(db_session)
    bot = await make_bot(db_session, owner=owner)

    # Act
    found = await BotRepository(db_session).get_live_bot_on_pair(10, PAIR, exclude_bot_id=bot.id)

    # Assert
    assert found is None


@pytest.mark.asyncio
async def test_another_running_bot_is_found_even_when_self_is_excluded(db_session):
    # Arrange
    owner = await make_user(db_session)
    await make_bot(db_session, owner=owner, bot_id="rival", status="running")
    mine = await make_bot(db_session, owner=owner, bot_id="mine", status="stopped")

    # Act
    found = await BotRepository(db_session).get_live_bot_on_pair(
        10, PAIR, statuses=("starting", "running"), exclude_bot_id=mine.id
    )

    # Assert
    assert found is not None and found.id == "rival"
