"""
Тест BotRepository.get_live_bots_on_key против настоящей (тестовой) БД.

Метод отвечает на вопрос «чьи депозиты уже заняли капитал этого биржевого ключа».
Цена ошибки — деньги: пропущенный бот означает, что сумма available_capital всех
ботов ключа превысит счёт, и биржа начнёт отбивать ордера при живых контейнерах.

Весь смысл метода — в SQL-фильтре, и фейковым репозиторием он не проверяется: фейк
вернул бы свой список при любом запросе. Поэтому тест интеграционный — выполняется
настоящий запрос к тестовой SQLite.
"""

import pytest

from src.models.bot import Bot
from src.models.user import User
from src.repositories.bot_repository import BotRepository


async def make_user(db_session, *, email: str = "owner@test.com") -> User:
    user = User(username="rodion", email=email, password_hash="hash")
    db_session.add(user)
    await db_session.flush()
    return user


async def make_bot(
    db_session,
    *,
    owner: User,
    bot_id: str,
    api_key_id: int | None = 10,
    dry_run: bool = False,
    status: str = "running",
    is_active: bool = True,
    stake_amount: float = 40.0,
) -> Bot:
    """Боевой бот на ключе №10 — то есть тот, чей депозит должен попасть в резерв.

    api_key_id заполнен числом без строки в exchange_api_keys: внешние ключи в SQLite
    не включены (см. CLAUDE.md), а запросу нужен только сам идентификатор.
    """
    bot = Bot(
        id=bot_id,
        user_id=owner.id,
        name=f"Бот {bot_id}",
        pair="SOL/USDT:USDT",
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
        stake_amount=stake_amount,
        tradable_balance_ratio=0.2,
        is_active=is_active,
    )
    db_session.add(bot)
    await db_session.flush()
    return bot


@pytest.mark.asyncio
async def test_bots_of_the_key_are_returned_in_any_status(db_session):
    # Arrange
    # Статус намеренно не фильтруется: остановленный или упавший бот может держать
    # открытую позицию, и его депозит по-прежнему занят.
    owner = await make_user(db_session)
    await make_bot(db_session, owner=owner, bot_id="running-bot", status="running")
    await make_bot(db_session, owner=owner, bot_id="stopped-bot", status="stopped")
    await make_bot(db_session, owner=owner, bot_id="error-bot", status="error")

    # Act
    bots = await BotRepository(db_session).get_live_bots_on_key(10)

    # Assert
    assert {bot.id for bot in bots} == {"running-bot", "stopped-bot", "error-bot"}


@pytest.mark.asyncio
async def test_dry_run_and_archived_bots_are_not_counted(db_session):
    # Arrange
    # Симуляция денег со счёта не берёт, а у архивированного бота контейнер удалён
    # вместе с позицией — держать под них капитал вечно значит запереть счёт.
    owner = await make_user(db_session)
    await make_bot(db_session, owner=owner, bot_id="live-bot")
    await make_bot(db_session, owner=owner, bot_id="dry-bot", dry_run=True)
    await make_bot(db_session, owner=owner, bot_id="archived-bot", is_active=False)

    # Act
    bots = await BotRepository(db_session).get_live_bots_on_key(10)

    # Assert
    assert [bot.id for bot in bots] == ["live-bot"]


@pytest.mark.asyncio
async def test_bots_of_another_key_are_not_counted(db_session):
    # Arrange
    # Деньги лежат на конкретном ключе; бот на другом ключе тратит другой счёт.
    owner = await make_user(db_session)
    await make_bot(db_session, owner=owner, bot_id="our-bot", api_key_id=10)
    await make_bot(db_session, owner=owner, bot_id="other-key-bot", api_key_id=11)
    await make_bot(db_session, owner=owner, bot_id="keyless-bot", api_key_id=None)

    # Act
    bots = await BotRepository(db_session).get_live_bots_on_key(10)

    # Assert
    assert [bot.id for bot in bots] == ["our-bot"]


@pytest.mark.asyncio
async def test_excluded_bot_is_not_counted(db_session):
    # Arrange
    # Так start_bot исключает самого себя: его депозит уже в базе, и без исключения
    # бот увидел бы в занятом собственные деньги и не стартовал бы никогда.
    owner = await make_user(db_session)
    await make_bot(db_session, owner=owner, bot_id="me")
    await make_bot(db_session, owner=owner, bot_id="rival")

    # Act
    bots = await BotRepository(db_session).get_live_bots_on_key(10, exclude_bot_id="me")

    # Assert
    assert [bot.id for bot in bots] == ["rival"]
