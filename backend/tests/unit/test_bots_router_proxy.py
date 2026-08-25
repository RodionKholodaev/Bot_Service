"""
Юнит-тесты двух прокси-ручек к freqtrade: GET /bots/{id}/logs и /bots/{id}/freqtrade/status.

Обе зовут async-методы BotService, и обе возвращали их результат без await. Наружу
уезжал объект корутины: FastAPI возвращённую корутину не ждёт, а сразу отдаёт в
jsonable_encoder, тот падает с ValueError — то есть клиент получал 500, а логи бота из
интерфейса было не посмотреть вообще. Ошибка дожила до продакшена ровно потому, что на
эти ручки не было ни одного теста.

Тесты проверяют не текст ответа, а его тип: обработчик обязан вернуть готовые данные,
а не корутину. Потерянный await красит их обратно.

Ни сети, ни docker, ни БД: репозиторий заменён фейком, docker-логи и клиент freqtrade —
подменёнными функциями.
"""

import inspect

import pytest

from src.core.exceptions import NotFoundError
from src.models.bot import Bot
from src.models.user import User
from src.routers.bots import freqtrade_status, get_logs
from src.services import bot_service as bot_service_module


class FakeBotRepo:
    """Fake вместо BotRepository — отдаёт заранее положенного бота по id."""

    def __init__(self, bots: list[Bot]):
        self._bots = bots

    async def get_bot_by_id(self, bot_id):
        for bot in self._bots:
            if bot.id == bot_id:
                return bot
        return None


class FakeApiKeysRepo:
    """Fake вместо ApiKeysRepository — прокси-ручки к ключам биржи не ходят."""


def make_user(*, user_id: int = 1) -> User:
    """Пользователь с минимумом полей — ручки берут только id."""
    return User(id=user_id, email="test@test.com")


def make_bot(*, bot_id: str = "bot-1", user_id: int = 1, container_id: str | None = "container-1") -> Bot:
    """Бот, принадлежащий пользователю: get_user_bot сверяет владельца и is_active."""
    return Bot(
        id=bot_id,
        user_id=user_id,
        name="Бот",
        pair="ETH/USDT:USDT",
        leverage=10,
        direction="long",
        strategy_preset="custom",
        entry_filters_long=[],
        entry_filters_short=[],
        take_profit={"0": 0.15},
        stop_loss=-0.1,
        dry_run=True,
        status="running",
        container_name="bot_test",
        container_id=container_id,
        api_port=9000,
        api_username="freqtrader",
        api_password="pass",
        stake_amount=100.0,
        tradable_balance_ratio=0.2,
        is_active=True,
    )


# ── Логи ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_logs_handler_returns_data_not_a_coroutine(monkeypatch):
    # Arrange
    user = make_user()
    bot = make_bot()
    monkeypatch.setattr(
        bot_service_module.docker_manager,
        "get_container_logs",
        lambda container_id, tail=200: "freqtrade log line",
    )

    # Act
    result = await get_logs(
        bot_id=bot.id,
        tail=50,
        current_user=user,
        bot_repo=FakeBotRepo([bot]), # type: ignore
        api_keys_repo=FakeApiKeysRepo(),
    )

    # Assert
    # Именно на этой проверке падала ручка: без await здесь лежала бы корутина,
    # которую FastAPI не умеет сериализовать.
    assert not inspect.iscoroutine(result)
    assert result == {"logs": "freqtrade log line"}


@pytest.mark.asyncio
async def test_logs_handler_passes_tail_through(monkeypatch):
    # Arrange
    user = make_user()
    bot = make_bot()
    calls: list[tuple[str, int]] = []

    def fake_logs(container_id, tail=200):
        calls.append((container_id, tail))
        return ""

    monkeypatch.setattr(bot_service_module.docker_manager, "get_container_logs", fake_logs)

    # Act
    await get_logs(
        bot_id=bot.id,
        tail=17,
        current_user=user,
        bot_repo=FakeBotRepo([bot]), # type: ignore
        api_keys_repo=FakeApiKeysRepo(),
    )

    # Assert
    assert calls == [("container-1", 17)]  # tail из запроса доезжает до docker


@pytest.mark.asyncio
async def test_logs_handler_rejects_someone_elses_bot():
    # Arrange
    bot = make_bot(user_id=1)
    stranger = make_user(user_id=2)

    # Act / Assert
    # 404, а не 403: по коду ответа нельзя отличить чужого бота от несуществующего
    with pytest.raises(NotFoundError):
        await get_logs(
            bot_id=bot.id,
            tail=50,
            current_user=stranger,
            bot_repo=FakeBotRepo([bot]), # type: ignore
            api_keys_repo=FakeApiKeysRepo(),
        )


# ── Статус из freqtrade ───────────────────────────────────


@pytest.mark.asyncio
async def test_status_handler_returns_data_not_a_coroutine(monkeypatch):
    # Arrange
    user = make_user()
    bot = make_bot()
    open_trades = [{"trade_id": 1, "pair": "ETH/USDT:USDT"}]
    monkeypatch.setattr(bot_service_module.freqtrade_client, "get_status", lambda b: open_trades)

    # Act
    result = await freqtrade_status(
        bot_id=bot.id,
        current_user=user,
        bot_repo=FakeBotRepo([bot]), # type: ignore
        api_keys_repo=FakeApiKeysRepo(),
    )

    # Assert
    assert not inspect.iscoroutine(result)
    assert result == open_trades


@pytest.mark.asyncio
async def test_status_handler_raises_when_bot_api_is_silent(monkeypatch):
    # Arrange
    user = make_user()
    bot = make_bot()
    # freqtrade_client глушит любую ошибку сети и возвращает None
    monkeypatch.setattr(bot_service_module.freqtrade_client, "get_status", lambda b: None)

    # Act / Assert
    with pytest.raises(NotFoundError):
        await freqtrade_status(
            bot_id=bot.id,
            current_user=user,
            bot_repo=FakeBotRepo([bot]), # type: ignore
            api_keys_repo=FakeApiKeysRepo(),
        )
