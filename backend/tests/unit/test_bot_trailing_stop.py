"""
Юнит-тесты на выключенный трейлинг-стоп.

Переключатель «Трейлинг стоп» стоял в форме создания бота, но никуда не уезжал:
в схеме BotCreate поля нет, а BotService всегда писал trailing_stop=False. Из
интерфейса его убрали, а не дотянули до бэкенда, потому что включать его в нынешнем
виде вредно: дистанция и порог захардкожены в шаблоне стратегии (0.001 / 0.002), а
freqtrade делит их на плечо — при x10 это 0.01% и 0.02% движения цены. Трейлинг
взводился бы почти сразу и обрезал каждый выигрыш до ~0.1% маржи вместо заданного
take-profit, оставляя убытки полноразмерными.

Тесты держат обе половины решения: бот создаётся с выключенным трейлингом, даже если
поле пришло в запросе руками, и в файл стратегии уезжает именно False. Включение
обратно должно быть осознанным действием, которое красит эти тесты.

Ни БД, ни docker, ни диск: репозитории заменены фейками, запись файлов бота — Spy,
а generate_strategy_file только читает шаблон с диска и возвращает строку.
"""

import pytest

from src.models.user import User
from src.schemas.bot import BotCreate
from src.services import bot_service as bot_service_module
from src.services.bot_service import BotService
from src.services.freqtrade_strategy import generate_strategy_file


class FakeApiKeysRepo:
    """Fake вместо ApiKeysRepository — ключей нет, dry-run бот за ними и не ходит."""

    async def get_api_key_by_id(self, key_id, user_id):
        return None


class FakeBotRepo:
    """Fake вместо BotRepository — запоминает созданных ботов, порт выдаёт фиксированный."""

    def __init__(self):
        self.created: list = []

    async def allocate_port(self):
        return 9000

    async def create(self, bot):
        self.created.append(bot)
        return bot


class SpyFileManager:
    """Spy вместо BotFileManager — вместо записи файлов бота запоминает аргументы."""

    def __init__(self):
        self.calls: list[dict] = []

    async def materialize_bot_files(self, bot, user_id, api_key, api_secret, iternal_api_port, jwt_secret, ws_token):
        self.calls.append({"bot": bot})


def make_user(*, user_id: int = 1) -> User:
    """Пользователь с минимумом полей — create_bot берёт только id."""
    return User(id=user_id, email="test@test.com")


def make_body(**overrides) -> BotCreate:
    """Валидное тело POST /bots: dry-run бот с плечом, при котором трейлинг и опасен."""
    data = {
        "name": "bot",
        "pair": "XRP/USDT:USDT",
        "leverage": 10,
        "direction": "long",
        "strategy_preset": "moderate",
        "entry_filters_long": [{"indicator": "rsi", "timeframe": "5m", "condition": "less", "value": 30}],
        "take_profit_percent": 1.5,
        "stop_loss_enabled": True,
        "stop_loss_percent": 1.0,
        "dry_run": True,
        "api_key_id": None,
        "stake_amount": 100.0,
        "tradable_balance_ratio": 0.5,
    }
    data.update(overrides)
    return BotCreate(**data)


@pytest.mark.asyncio
async def test_created_bot_has_trailing_stop_disabled(monkeypatch):
    # Arrange
    spy_files = SpyFileManager()
    monkeypatch.setattr(bot_service_module, "BotFileManager", spy_files)
    bot_repo = FakeBotRepo()

    # Act
    bot = await BotService(bot_repo, FakeApiKeysRepo()).create_bot(make_user(), make_body())  # type: ignore

    # Assert
    assert bot.trailing_stop is False
    # trailing_config пустует намеренно: осмысленных чисел для трейлинга у нас пока нет,
    # и класть в неё захардкоженные 0.001/0.002 было бы хуже, чем не класть ничего
    assert bot.trailing_config is None
    # в файлы бота уходит тот же самый объект, то есть и в стратегию — выключенный трейлинг
    assert spy_files.calls[0]["bot"] is bot


@pytest.mark.asyncio
async def test_trailing_stop_sent_by_client_does_not_reach_the_bot(monkeypatch):
    # Arrange
    spy_files = SpyFileManager()
    monkeypatch.setattr(bot_service_module, "BotFileManager", spy_files)
    bot_repo = FakeBotRepo()
    # поля в схеме нет, но BotCreate не запрещает лишние ключи — pydantic их молча выбросит;
    # проверяем весь путь целиком, потому что защит здесь две и упасть должна любая из них
    body = make_body(trailing_stop=True)
    assert not hasattr(body, "trailing_stop")

    # Act
    bot = await BotService(bot_repo, FakeApiKeysRepo()).create_bot(make_user(), body)  # type: ignore

    # Assert
    assert bot.trailing_stop is False


def test_generated_strategy_has_trailing_stop_off():
    # Arrange / Act
    rendered = generate_strategy_file(
        leverage=10,
        can_short=False,
        entry_filters_long=[{"indicator": "rsi", "timeframe": "5m", "condition": "less", "value": 30}],
        entry_filters_short=[],
        take_profit={"0": 0.015},
        stoploss=-0.01,
        trailing_stop=False,
    )

    # Assert
    # именно эта строка доезжает до freqtrade как trailing_stop стратегии
    assert "TRAILING_STOP = False" in rendered
    assert "TRAILING_STOP = True" not in rendered
    # плейсхолдер обязан быть подставлен: незаменённый {{...}} — синтаксическая ошибка
    # в файле стратегии, и контейнер бота не поднимется вовсе
    assert "{{TRAILING_STOP}}" not in rendered
