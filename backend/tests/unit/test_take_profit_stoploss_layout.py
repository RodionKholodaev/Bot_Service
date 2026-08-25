"""
Юнит-тесты раскладки take profit и stop loss из процентов пользователя в формат freqtrade.

Проценты в форме — это движение ЦЕНЫ: «take profit 1.5%» значит «цена прошла полтора
процента», и плечо на эту величину не влияет. freqtrade же меряет minimal_roi и stoploss
в долях МАРЖИ, а маржа в leverage раз меньше позиции. Перевод одного в другое живёт
ровно в двух функциях, и до этих тестов он не был покрыт ничем.

Раньше умножения на плечо не было вовсе: «1.5%» уезжало как 1.5% маржи, то есть 0.15%
движения цены при x10 — в десять раз ближе, чем ожидал пользователь, и внутри спреда.
Это тот же класс ошибки, на котором проект уже обжёгся с депозитом (коммит f1f790e):
раскладка чисел по ключам freqtrade, которую он молча принимает любой.

Ни БД, ни docker, ни диск: две функции чистые, а сборку бота целиком проверяем на
фейковых репозиториях и Spy вместо BotFileManager.
"""

import pytest
from pydantic import ValidationError

from src.models.user import User
from src.schemas.bot import BotCreate
from src.services import bot_service as bot_service_module
from src.services.bot_service import BotService


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
    """Валидное тело POST /bots с разумными дефолтами."""
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


# ──────────────────────────────────────────────
# Перевод процентов цены в доли маржи
# ──────────────────────────────────────────────


def test_take_profit_percent_is_price_movement_not_margin():
    # Arrange / Act
    roi = BotService._build_take_profit(1.5, leverage=10)

    # Assert
    # 1.5% движения цены при x10 — это 15% маржи: доля, которой оперирует minimal_roi
    assert roi == {"0": 0.15}


def test_take_profit_scales_with_leverage_at_the_same_price_movement():
    # Arrange / Act
    # одно и то же движение цены при разном плече даёт разный minimal_roi —
    # именно потому, что цель по цене от плеча не зависит
    at_x1 = BotService._build_take_profit(1.5, leverage=1)
    at_x10 = BotService._build_take_profit(1.5, leverage=10)
    at_x20 = BotService._build_take_profit(1.5, leverage=20)

    # Assert
    assert at_x1 == {"0": 0.015}
    assert at_x10 == {"0": 0.15}
    assert at_x20 == {"0": 0.3}


def test_stoploss_percent_is_price_movement_not_margin():
    # Arrange / Act
    stoploss = BotService._build_stoploss(True, 1.0, leverage=10)

    # Assert
    # 1% движения цены при x10 — это 10% маржи, и знак минус: freqtrade ждёт долю убытка
    assert stoploss == -0.1


def test_stoploss_scales_with_leverage_at_the_same_price_movement():
    # Arrange / Act / Assert
    assert BotService._build_stoploss(True, 1.0, leverage=1) == -0.01
    assert BotService._build_stoploss(True, 1.0, leverage=5) == -0.05


def test_disabled_stoploss_holds_position_until_liquidation():
    # Arrange / Act / Assert
    # -0.99 — «стопа нет»: позиция держится почти до полной потери маржи. Плечо здесь
    # ни при чём, доля маржи задана напрямую
    assert BotService._build_stoploss(False, None, leverage=10) == -0.99
    assert BotService._build_stoploss(False, None, leverage=1) == -0.99


def test_disabled_stoploss_ignores_the_given_percent():
    # Arrange / Act / Assert
    # галочка выключена — присланное число не должно случайно доехать до стратегии
    assert BotService._build_stoploss(False, 2.0, leverage=10) == -0.99


# ──────────────────────────────────────────────
# Граница: стоп не может быть дальше маржи
# ──────────────────────────────────────────────


def test_stoploss_that_eats_the_whole_margin_is_rejected():
    # Arrange / Act / Assert
    # 10% движения цены при x10 — это вся маржа, stoploss = -1.0. Позиции к этому моменту
    # уже нет, её ликвидировали, а freqtrade такой стоп не принимает и падает на старте
    with pytest.raises(ValidationError) as exc:
        make_body(leverage=10, stop_loss_percent=10.0)

    # в тексте ошибки — предел именно для этого плеча, иначе пользователю нечего чинить
    assert "10.0%" in str(exc.value)


def test_stoploss_within_the_margin_is_accepted():
    # Arrange / Act
    body = make_body(leverage=10, stop_loss_percent=9.0)

    # Assert
    assert body.stop_loss_percent == 9.0


def test_same_percent_is_rejected_or_accepted_depending_on_leverage():
    # Arrange / Act / Assert
    # 5% движения цены — нормальный стоп при x10 (половина маржи) и невозможный при x20
    assert make_body(leverage=10, stop_loss_percent=5.0).stop_loss_percent == 5.0
    with pytest.raises(ValidationError):
        make_body(leverage=20, stop_loss_percent=5.0)


def test_disabled_stoploss_is_not_bound_by_leverage():
    # Arrange / Act
    # Процент оставлен в теле намеренно: галочка выключена, и число в поле формы никуда
    # не девается. Проверять границу для стопа, которого не будет, нельзя — запрос был бы
    # отбит на ровном месте. 10% при x20 — это две маржи, то есть заведомо за границей.
    body = make_body(leverage=20, stop_loss_enabled=False, stop_loss_percent=10.0)

    # Assert
    assert body.stop_loss_enabled is False
    # и до стратегии всё равно доедет «стопа нет», а не присланное число
    assert BotService._build_stoploss(body.stop_loss_enabled, body.stop_loss_percent, body.leverage) == -0.99


# ──────────────────────────────────────────────
# Сборка бота целиком: плечо доезжает до обеих функций
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_created_bot_stores_price_percents_converted_by_leverage(monkeypatch):
    # Arrange
    spy_files = SpyFileManager()
    monkeypatch.setattr(bot_service_module, "BotFileManager", spy_files)
    bot_repo = FakeBotRepo()

    # Act
    bot = await BotService(bot_repo, FakeApiKeysRepo()).create_bot(  # type: ignore
        make_user(),
        make_body(leverage=10, take_profit_percent=1.5, stop_loss_percent=1.0),
    )

    # Assert
    # без передачи плеча в обе функции здесь лежали бы 0.015 и -0.01 — то есть 0.15%
    # и 0.1% движения цены вместо заданных полутора и одного процента
    assert bot.take_profit == {"0": 0.15}
    assert bot.stop_loss == -0.1
    # в файлы бота уходит тот же объект, значит эти же числа попадут в стратегию
    assert spy_files.calls[0]["bot"] is bot
