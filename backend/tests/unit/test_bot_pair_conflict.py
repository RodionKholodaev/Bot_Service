"""
Юнит-тесты BotService: один биржевой ключ — одна пара — один боевой бот.

Два бота на SOL/USDT с одним ключом — это одна позиция на Bybit: биржа их нетит.
Вход второго увеличит позицию первого, а стоп первого закроет её целиком, вместе
с чужой частью. При этом у каждого бота свой tradesv3.sqlite, общей картины нет ни
у кого, и комиссия сервиса считается с разъехавшихся цифр. Поэтому и create_bot, и
start_bot отбивают такое 409-м.

Здесь проверяется поведение сервиса: когда он вообще спрашивает репозиторий, с
какими аргументами и что делает с ответом. Сам SQL-фильтр фейком не проверить —
на него есть отдельный интеграционный тест
(tests/integration/test_bot_pair_conflict_repository.py).

Ни БД, ни docker, ни диск: репозитории заменены фейками, запись файлов бота — Spy.
"""

import pytest

from src.core.crypto import encrypt
from src.core.exceptions import ConflictError
from src.models.bot import Bot
from src.models.exchange_api_key import ExchangeApiKey
from src.models.user import User
from src.schemas.bot import BotCreate
from src.services import bot_service as bot_service_module
from src.services.bot_service import BotService
from tests.fakes.test_exchange_account import FakeExchangeAccountClient

PAIR = "SOL/USDT:USDT"


# ──────────────────────────────────────────────
# Фабрики и фейки
# ──────────────────────────────────────────────


def make_user(*, user_id: int = 1) -> User:
    """Баланс задан явно: колоночный default=0.0 на несохранённом объекте не
    применяется, а create_bot сверяет баланс с порогом — на None сравнение упало бы."""
    return User(id=user_id, email="test@test.com", service_balance=10_000.0)


def make_api_key(*, key_id: int = 10, owner_id: int = 1) -> ExchangeApiKey:
    return ExchangeApiKey(
        id=key_id,
        user_id=owner_id,
        exchange="bybit",
        label="Ключ",
        api_key_encrypted=encrypt("key"),
        api_secret_encrypted=encrypt("secret"),
        is_active=True,
    )


def make_bot(**overrides) -> Bot:
    """Уже существующий боевой бот — тот, кого фейковый репозиторий выдаёт как соперника.

    dry_run=False задан явно по той же причине, что и баланс выше: на несохранённом
    объекте колоночный default не применяется.
    """
    defaults = {
        "id": "rival",
        "user_id": 1,
        "name": "Старый бот",
        "pair": PAIR,
        "api_key_id": 10,
        "dry_run": False,
        "status": "running",
    }
    defaults.update(overrides)
    return Bot(**defaults)


class FakeBotRepo:
    """Fake вместо BotRepository — запоминает запросы о занятой паре и отдаёт заготовку.

    Настоящий SQL-фильтр здесь не воспроизводится намеренно: аргументы запроса
    проверяются отдельно (`pair_queries`), а сам фильтр — интеграционным тестом.
    """

    def __init__(self, rival: Bot | None = None):
        self.rival = rival
        self.created: list[Bot] = []
        self.statuses: list[str] = []
        self.pair_queries: list[dict] = []

    async def get_live_bot_on_pair(self, api_key_id, pair, *, statuses=None, exclude_bot_id=None):
        self.pair_queries.append(
            {
                "api_key_id": api_key_id,
                "pair": pair,
                "statuses": statuses,
                "exclude_bot_id": exclude_bot_id,
            }
        )
        return self.rival

    async def get_live_bots_on_key(self, api_key_id, *, exclude_bot_id=None):
        # Занятый капитал в этих тестах не проверяется — на него есть
        # tests/unit/test_capital_guard.py; ключ здесь всегда пустой.
        return []

    async def allocate_port(self):
        return 9000

    async def create(self, bot):
        self.created.append(bot)
        return bot

    async def get_user(self, user_id):
        return make_user(user_id=user_id)

    async def change_bot_status(self, status, bot):
        self.statuses.append(status)
        bot.status = status
        return bot

    async def add_error_message(self, error, bot):
        bot.error_message = error
        return bot

    async def change_container_id(self, container_id, bot):
        bot.container_id = container_id
        return bot


class FakeApiKeysRepo:
    """Fake вместо ApiKeysRepository — отдаёт ключ, только если совпал и id, и владелец."""

    def __init__(self, keys: list[ExchangeApiKey]):
        self._keys = keys

    async def get_api_key_by_id(self, key_id, user_id):
        for key in self._keys:
            if key.id == key_id and key.user_id == user_id:
                return key
        return None


class SpyFileManager:
    """Spy вместо BotFileManager — вместо записи файлов бота запоминает вызовы."""

    def __init__(self):
        self.calls: list[dict] = []

    async def materialize_bot_files(self, bot, user_id, api_key, api_secret, iternal_api_port, jwt_secret, ws_token):
        self.calls.append({"bot": bot, "user_id": user_id})


def make_body(**overrides) -> BotCreate:
    """Валидное тело POST /bots: боевой бот на SOL с ключом №10."""
    data = {
        "name": "Новый бот",
        "pair": PAIR,
        "leverage": 5,
        "direction": "long",
        "strategy_preset": "moderate",
        "entry_filters_long": [{"indicator": "rsi", "timeframe": "5m", "condition": "less", "value": 30}],
        "take_profit_percent": 4.0,
        "stop_loss_enabled": True,
        "stop_loss_percent": 2.0,
        "dry_run": False,
        "api_key_id": 10,
        "stake_amount": 100.0,
        "tradable_balance_ratio": 0.5,
    }
    data.update(overrides)
    return BotCreate(**data)


@pytest.fixture
def spy_files(monkeypatch):
    """Подменяет BotFileManager внутри bot_service — тесты не пишут на диск.

    Патчим по пути `src.services.bot_service.BotFileManager`: модуль импортировал имя
    к себе, и подмена в модуле-источнике не подействовала бы.
    """
    spy = SpyFileManager()
    monkeypatch.setattr(bot_service_module, "BotFileManager", spy)
    return spy


# ──────────────────────────────────────────────
# Создание бота
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_second_bot_on_same_key_and_pair_is_rejected(spy_files):
    # Arrange
    user = make_user()
    bot_repo = FakeBotRepo(rival=make_bot())

    # Act / Assert
    # 409, а не 400: запрос сам по себе валиден, мешает состояние — уже занятая пара.
    with pytest.raises(ConflictError) as exc:
        await BotService(bot_repo, FakeApiKeysRepo([make_api_key()]), FakeExchangeAccountClient()).create_bot(
            user, make_body()
        )  # type: ignore

    # текст пользователю на русском и называет обоих участников конфликта
    assert "Старый бот" in exc.value.detail
    assert PAIR in exc.value.detail
    # отказ случился до записи в БД и до создания файлов — порт тоже не занят
    assert bot_repo.created == []
    assert spy_files.calls == []


@pytest.mark.asyncio
async def test_creation_asks_about_any_status_of_rival(spy_files):
    # Arrange
    # На создании статус соперника не важен: остановленный или упавший бот тоже может
    # держать открытую позицию на бирже, а созданный просто ждёт кнопки «Запустить».
    bot_repo = FakeBotRepo(rival=None)

    # Act
    await BotService(bot_repo, FakeApiKeysRepo([make_api_key()]), FakeExchangeAccountClient()).create_bot(
        make_user(), make_body()
    )  # type: ignore

    # Assert
    assert bot_repo.pair_queries == [
        {"api_key_id": 10, "pair": PAIR, "statuses": None, "exclude_bot_id": None},
    ]


@pytest.mark.asyncio
async def test_bot_on_free_pair_is_created(spy_files):
    # Arrange
    bot_repo = FakeBotRepo(rival=None)

    # Act
    bot = await BotService(bot_repo, FakeApiKeysRepo([make_api_key()]), FakeExchangeAccountClient()).create_bot(  # type: ignore
        make_user(), make_body(pair="XRP/USDT:USDT")
    )

    # Assert
    assert bot_repo.created == [bot]
    assert len(spy_files.calls) == 1


@pytest.mark.asyncio
async def test_dry_run_bot_is_created_on_busy_pair(spy_files):
    # Arrange
    # Симуляция реальных ордеров не ставит: позицию боевого бота она не тронет.
    bot_repo = FakeBotRepo(rival=make_bot())

    # Act
    bot = await BotService(bot_repo, FakeApiKeysRepo([make_api_key()]), FakeExchangeAccountClient()).create_bot(  # type: ignore
        make_user(), make_body(dry_run=True)
    )

    # Assert
    assert bot_repo.created == [bot]
    # репозиторий об этой паре даже не спрашивали
    assert bot_repo.pair_queries == []


@pytest.mark.asyncio
async def test_bot_without_api_key_does_not_check_the_pair(spy_files):
    # Arrange
    # Без ключа бот ни с кем не делит счёт на бирже. Спрашивать репозиторий тут не
    # просто лишнее, а опасно: api_key_id=None в SQLAlchemy превращается в IS NULL,
    # и такой запрос собрал бы всех бесключевых ботов на этой паре.
    bot_repo = FakeBotRepo(rival=make_bot())

    # Act
    await BotService(bot_repo, FakeApiKeysRepo([]), FakeExchangeAccountClient()).create_bot(  # type: ignore
        make_user(), make_body(api_key_id=None, dry_run=True)
    )

    # Assert
    assert bot_repo.pair_queries == []


# ──────────────────────────────────────────────
# Запуск бота
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_is_rejected_while_another_bot_trades_the_pair():
    # Arrange
    mine = make_bot(id="mine", name="Мой бот", status="stopped")
    bot_repo = FakeBotRepo(rival=make_bot(id="rival", name="Старый бот"))

    # Act / Assert
    with pytest.raises(ConflictError) as exc:
        await BotService(bot_repo, FakeApiKeysRepo([]), FakeExchangeAccountClient()).start_bot(mine)  # type: ignore

    assert "Старый бот" in exc.value.detail
    # Статус не тронут: проверка стоит до перевода в "starting", иначе отбитый бот
    # завис бы в этом статусе навсегда.
    assert bot_repo.statuses == []
    assert mine.status == "stopped"


@pytest.mark.asyncio
async def test_start_asks_only_about_trading_rivals_and_excludes_itself(tmp_path, monkeypatch):
    # Arrange
    # На запуске, в отличие от создания, считаются только реально торгующие соседи:
    # иначе пару дубликатов, заведённых до появления проверки, нельзя было бы
    # запустить ни по одному. И себя из запроса исключаем — create_bot уже записал
    # бота в БД, и router зовёт start_bot сразу за ним.
    mine = make_bot(id="mine", status="created")
    bot_repo = FakeBotRepo(rival=None)

    # start_bot читает config.json с диска и поднимает контейнер — подменяем и то, и другое
    (tmp_path / mine.id).mkdir()
    (tmp_path / mine.id / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bot_service_module.settings, "BOTS_DATA_DIR", tmp_path)
    monkeypatch.setattr(bot_service_module.docker_manager, "ensure_image", lambda: None)
    monkeypatch.setattr(
        bot_service_module.docker_manager,
        "run_bot_container",
        lambda container_name, bot_data_dir, api_port_external: type("C", (), {"id": "container-1"})(),
    )

    # Act
    await BotService(bot_repo, FakeApiKeysRepo([]), FakeExchangeAccountClient()).start_bot(mine)  # type: ignore

    # Assert
    assert bot_repo.pair_queries == [
        {
            "api_key_id": 10,
            "pair": PAIR,
            "statuses": ("starting", "running"),
            "exclude_bot_id": "mine",
        },
    ]
    assert mine.status == "running"


@pytest.mark.asyncio
async def test_dry_run_bot_start_does_not_check_the_pair(tmp_path, monkeypatch):
    # Arrange
    mine = make_bot(id="mine", dry_run=True, status="stopped")
    bot_repo = FakeBotRepo(rival=make_bot())

    (tmp_path / mine.id).mkdir()
    (tmp_path / mine.id / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bot_service_module.settings, "BOTS_DATA_DIR", tmp_path)
    monkeypatch.setattr(bot_service_module.docker_manager, "ensure_image", lambda: None)
    monkeypatch.setattr(
        bot_service_module.docker_manager,
        "run_bot_container",
        lambda container_name, bot_data_dir, api_port_external: type("C", (), {"id": "container-1"})(),
    )

    # Act
    await BotService(bot_repo, FakeApiKeysRepo([]), FakeExchangeAccountClient()).start_bot(mine)  # type: ignore

    # Assert
    assert bot_repo.pair_queries == []
    assert mine.status == "running"
