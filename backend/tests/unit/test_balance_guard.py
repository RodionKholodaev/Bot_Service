"""
Юнит-тесты для balance_guard — порога сервисного баланса.

Здесь решается, торгует пользователь дальше или нет, поэтому важны границы:
ровно порог (торгуем) против «на копейку ниже» (останавливаем), dry-run боты,
которые порог не ограничивает вообще, и то, какие боты возвращаются воркеру
после остановки — оставленный в цикле убитый бот уехал бы в статус "error"
с критическим алертом, хотя его выключили штатно.

Второй блок — тот же порог на входе: BotService.create_bot и BotService.start_bot
не должны пускать боевого бота при недостаточном балансе.

Ни БД, ни Docker: сессия, репозитории и запись файлов бота подменяются фейками,
docker_manager — через monkeypatch. BotRepository в первом блоке настоящий: он
только пишет поля объекта и зовёт flush/refresh, которые фейковая сессия умеет —
так тесты проверяют и его тоже.
"""

import pytest

from src.config import settings
from src.core.exceptions import PaymentRequiredError
from src.models.bot import Bot
from src.models.user import User
from src.schemas.bot import BotCreate
from src.services import balance_guard, docker_manager
from src.services import bot_service as bot_service_module
from src.services.balance_guard import (
    is_balance_sufficient,
    stop_bots_for_low_balance,
    stop_bots_of_low_balance_users,
)
from src.services.bot_service import BotService

MIN_BALANCE = settings.MIN_SERVICE_BALANCE_RUB


# ──────────────────────────────────────────────
# Фабрики и фейки
# ──────────────────────────────────────────────


def make_user(*, user_id: int = 1, service_balance: float = MIN_BALANCE) -> User:
    """Пользователь в памяти; по умолчанию баланс ровно на пороге."""
    return User(id=user_id, service_balance=service_balance)


def make_bot(**overrides) -> Bot:
    """Работающий боевой бот с контейнером.

    dry_run=False задан явно: колоночный default=True на несохранённом объекте не
    применяется, там лежал бы None. Тест про остановку прошёл бы, но по случайности
    (None ложен) и перестал бы что-либо доказывать.
    """
    defaults = {
        "id": "bot-1",
        "user_id": 1,
        "status": "running",
        "dry_run": False,
        "container_id": "container-1",
    }
    defaults.update(overrides)
    return Bot(**defaults)


class FakeSession:
    """Fake вместо AsyncSession — считает коммиты, ничего не пишет."""

    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1

    async def flush(self):
        pass

    async def refresh(self, obj):
        pass


class FakeUserRepository:
    """Fake вместо UserRepository — отдаёт пользователей из словаря, без запроса в БД."""

    def __init__(self, users: dict[int, User]):
        self._users = users

    async def get_user_by_id(self, user_id: int) -> User | None:
        return self._users.get(user_id)


@pytest.fixture
def stopped_containers(monkeypatch):
    """Подменяет docker_manager — тесты не трогают реальный Docker."""
    stopped: list[str] = []
    monkeypatch.setattr(docker_manager, "stop_container", lambda cid: stopped.append(cid))
    return stopped


@pytest.fixture
def known_users(monkeypatch):
    """Подменяет UserRepository внутри balance_guard пользователями из словаря.

    Патчим по пути `src.services.balance_guard.UserRepository`: модуль импортировал
    класс к себе, и подмена в модуле-источнике на уже импортированное имя
    не подействовала бы.
    """

    def _set(*users: User) -> None:
        by_id = {user.id: user for user in users}
        monkeypatch.setattr(balance_guard, "UserRepository", lambda db: FakeUserRepository(by_id))

    return _set


# ──────────────────────────────────────────────
# Граница порога
# ──────────────────────────────────────────────


def test_balance_exactly_at_threshold_is_sufficient():
    # Arrange
    # Ровно порог — ещё можно торговать: проверка идёт по >=, а не по >.
    user = make_user(service_balance=MIN_BALANCE)

    # Act / Assert
    assert is_balance_sufficient(user) is True


def test_balance_one_kopeck_below_threshold_is_not_sufficient():
    # Arrange
    user = make_user(service_balance=MIN_BALANCE - 0.01)

    # Act / Assert
    assert is_balance_sufficient(user) is False


def test_negative_balance_is_not_sufficient():
    # Arrange
    # Баланс уходит в минус штатно: комиссия списывается полностью и не клампится
    # порогом (см. test_comission_service.py) — долг остаётся на балансе.
    user = make_user(service_balance=-500.0)

    # Act / Assert
    assert is_balance_sufficient(user) is False


# ──────────────────────────────────────────────
# Остановка ботов конкретного пользователя
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_running_live_bot_is_stopped_with_message(stopped_containers):
    # Arrange
    user = make_user(service_balance=0.0)
    bot = make_bot()
    db = FakeSession()

    # Act
    stopped = await stop_bots_for_low_balance(db, user, [bot])  # type: ignore

    # Assert
    assert stopped == [bot]
    # "stopped", а не "error": бот не сломался, его выключил сервис, и пользователь
    # запустит его обратно обычной кнопкой после пополнения.
    assert bot.status == "stopped"
    assert bot.error_message == balance_guard.stopped_message()
    assert stopped_containers == ["container-1"]
    # Статус коммитим до остановки контейнера: если docker откажет, в БД он всё
    # равно должен остаться.
    assert db.commits == 1


@pytest.mark.asyncio
async def test_dry_run_bot_is_not_stopped(stopped_containers):
    # Arrange
    # За dry-run комиссия не берётся вообще, сервису он ничего не стоит —
    # порог его не касается.
    user = make_user(service_balance=0.0)
    bot = make_bot(dry_run=True)
    db = FakeSession()

    # Act
    stopped = await stop_bots_for_low_balance(db, user, [bot])  # type: ignore

    # Assert
    assert stopped == []
    assert bot.status == "running"
    assert bot.error_message is None
    assert stopped_containers == []
    assert db.commits == 0  # трогать нечего — и коммита нет


@pytest.mark.asyncio
async def test_already_stopped_bot_is_not_touched(stopped_containers):
    # Arrange
    # Бот, остановленный прошлым циклом воркера: перезаписывать статус и заново
    # дёргать docker каждые 30 секунд не за чем.
    user = make_user(service_balance=0.0)
    bot = make_bot(status="stopped")
    db = FakeSession()

    # Act
    stopped = await stop_bots_for_low_balance(db, user, [bot])  # type: ignore

    # Assert
    assert stopped == []
    assert stopped_containers == []
    assert db.commits == 0


@pytest.mark.asyncio
async def test_bot_without_container_is_marked_stopped_anyway(stopped_containers):
    # Arrange
    bot = make_bot(container_id=None)
    db = FakeSession()

    # Act
    stopped = await stop_bots_for_low_balance(db, make_user(service_balance=0.0), [bot])  # type: ignore

    # Assert: останавливать нечего, но статус и сообщение всё равно должны появиться
    assert stopped == [bot]
    assert bot.status == "stopped"
    assert stopped_containers == []


@pytest.mark.asyncio
async def test_docker_failure_does_not_undo_stopped_status(monkeypatch):
    # Arrange
    # Docker недоступен. Статус уже в БД (закоммичен до остановки), и падение
    # docker'а не должно ни ронять воркер, ни возвращать бота в "running".
    def explode(container_id):
        raise RuntimeError("docker is down")

    monkeypatch.setattr(docker_manager, "stop_container", explode)
    bot = make_bot()
    db = FakeSession()

    # Act
    stopped = await stop_bots_for_low_balance(db, make_user(service_balance=0.0), [bot])  # type: ignore

    # Assert
    assert stopped == [bot]
    assert bot.status == "stopped"
    assert db.commits == 1


# ──────────────────────────────────────────────
# Отбор ботов для воркера
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bots_of_solvent_user_are_returned_untouched(known_users, stopped_containers):
    # Arrange
    user = make_user(user_id=1, service_balance=MIN_BALANCE)
    bot = make_bot(user_id=1)
    known_users(user)
    db = FakeSession()

    # Act
    allowed = await stop_bots_of_low_balance_users(db, [bot])  # type: ignore

    # Assert
    assert allowed == [bot]
    assert bot.status == "running"
    assert stopped_containers == []


@pytest.mark.asyncio
async def test_stopped_bot_is_excluded_and_others_are_kept(known_users, stopped_containers):
    # Arrange
    poor = make_user(user_id=1, service_balance=MIN_BALANCE - 0.01)
    rich = make_user(user_id=2, service_balance=MIN_BALANCE * 10)
    poor_live = make_bot(id="poor-live", user_id=1, container_id="c-poor")
    poor_dry = make_bot(id="poor-dry", user_id=1, dry_run=True, container_id="c-dry")
    rich_live = make_bot(id="rich-live", user_id=2, container_id="c-rich")
    known_users(poor, rich)
    db = FakeSession()

    # Act
    allowed = await stop_bots_of_low_balance_users(db, [poor_live, poor_dry, rich_live])  # type: ignore

    # Assert
    # Остановленного бота нельзя оставлять в цикле: ping в убитый контейнер не пройдёт,
    # и через MAX_PING_MISSES бот уехал бы в "error" с критическим алертом.
    assert {bot.id for bot in allowed} == {"poor-dry", "rich-live"}
    assert poor_live.status == "stopped"
    assert poor_dry.status == "running"
    assert rich_live.status == "running"
    assert stopped_containers == ["c-poor"]


@pytest.mark.asyncio
async def test_bots_of_unknown_user_are_left_alone(known_users, stopped_containers):
    # Arrange
    # Осиротевший бот: внешние ключи в SQLite не работают, и удалённый пользователь
    # оставляет своих ботов в таблице. Решать за него нечего — отдаём воркеру как есть.
    bot = make_bot(user_id=42)
    known_users()  # пользователей нет вовсе
    db = FakeSession()

    # Act
    allowed = await stop_bots_of_low_balance_users(db, [bot])  # type: ignore

    # Assert
    assert allowed == [bot]
    assert bot.status == "running"
    assert stopped_containers == []


# ──────────────────────────────────────────────
# Тот же порог на входе: создание и запуск бота
# ──────────────────────────────────────────────


class FakeBotRepo:
    """Fake вместо BotRepository — держит ботов в памяти, порт выдаёт фиксированный."""

    def __init__(self, owner: User | None = None):
        self.owner = owner
        self.created: list[Bot] = []
        self.statuses: list[str] = []

    async def allocate_port(self):
        return 9000

    async def get_live_bot_on_pair(self, api_key_id, pair, *, statuses=None, exclude_bot_id=None):
        # пара всегда свободна: запрет «один ключ — одна пара» проверяется отдельно,
        # в test_bot_pair_conflict.py
        return None

    async def create(self, bot):
        self.created.append(bot)
        return bot

    async def get_user(self, user_id):
        return self.owner

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


class SpyFileManager:
    """Spy вместо BotFileManager — вместо записи файлов бота запоминает вызовы."""

    def __init__(self):
        self.calls: list[dict] = []

    async def materialize_bot_files(self, bot, user_id, api_key, api_secret, iternal_api_port, jwt_secret, ws_token):
        self.calls.append({"bot": bot, "user_id": user_id})


class FakeApiKeysRepo:
    """Fake вместо ApiKeysRepository — ключей нет, боты здесь создаются без биржевого ключа."""

    async def get_api_key_by_id(self, key_id, user_id):
        return None


def make_body(**overrides) -> BotCreate:
    """Валидное тело POST /bots. api_key_id=None — биржевой ключ этим тестам не нужен."""
    data = {
        "name": "bot",
        "pair": "XRP/USDT:USDT",
        "leverage": 5,
        "direction": "long",
        "strategy_preset": "moderate",
        "entry_filters_long": [{"indicator": "rsi", "timeframe": "5m", "condition": "less", "value": 30}],
        "take_profit_percent": 4.0,
        "stop_loss_enabled": True,
        "stop_loss_percent": 2.0,
        "dry_run": False,
        "api_key_id": None,
        "stake_amount": 100.0,
        "tradable_balance_ratio": 0.5,
    }
    data.update(overrides)
    return BotCreate(**data)


@pytest.mark.asyncio
async def test_live_bot_is_not_created_below_threshold(monkeypatch):
    # Arrange
    spy_files = SpyFileManager()
    monkeypatch.setattr(bot_service_module, "BotFileManager", spy_files)
    user = make_user(service_balance=MIN_BALANCE - 0.01)
    bot_repo = FakeBotRepo()

    # Act / Assert
    # 402, а не 400: у отказа единственная причина — деньги, и фронт по коду
    # отличает его от невалидной формы.
    with pytest.raises(PaymentRequiredError):
        await BotService(bot_repo, FakeApiKeysRepo()).create_bot(user, make_body())  # type: ignore

    # отказ случился до записи в БД и до создания файлов — порт тоже не занят
    assert bot_repo.created == []
    assert spy_files.calls == []


@pytest.mark.asyncio
async def test_dry_run_bot_is_created_below_threshold(monkeypatch):
    # Arrange
    # Порог не касается симуляции: комиссии за неё нет, сервису она ничего не стоит.
    spy_files = SpyFileManager()
    monkeypatch.setattr(bot_service_module, "BotFileManager", spy_files)
    user = make_user(service_balance=0.0)
    bot_repo = FakeBotRepo()

    # Act
    bot = await BotService(bot_repo, FakeApiKeysRepo()).create_bot(user, make_body(dry_run=True))  # type: ignore

    # Assert
    assert bot_repo.created == [bot]
    assert len(spy_files.calls) == 1


@pytest.mark.asyncio
async def test_live_bot_is_not_started_below_threshold():
    # Arrange
    # /bots/{id}/start дёргается и по боту, который воркер уже остановил из-за баланса.
    owner = make_user(service_balance=MIN_BALANCE - 0.01)
    bot = make_bot(status="stopped")
    bot_repo = FakeBotRepo(owner=owner)

    # Act / Assert
    with pytest.raises(PaymentRequiredError):
        await BotService(bot_repo, FakeApiKeysRepo()).start_bot(bot)  # type: ignore

    # Статус не тронут: проверка стоит до перевода в "starting", иначе отбитый бот
    # завис бы в этом статусе навсегда.
    assert bot_repo.statuses == []
    assert bot.status == "stopped"


@pytest.mark.asyncio
async def test_successful_start_clears_low_balance_message(monkeypatch, tmp_path):
    # Arrange
    # Пользователь пополнил баланс и запускает бота обратно. Сообщение об остановке
    # обязано исчезнуть — иначе под работающим ботом на /home висит старый текст.
    owner = make_user(service_balance=MIN_BALANCE)
    bot = make_bot(status="stopped")
    bot.error_message = balance_guard.stopped_message()
    bot_repo = FakeBotRepo(owner=owner)

    # start_bot читает config.json бота с диска и поднимает контейнер — подменяем и то,
    # и другое: настоящий docker в юнит-тестах не нужен.
    (tmp_path / bot.id).mkdir()
    (tmp_path / bot.id / "config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bot_service_module.settings, "BOTS_DATA_DIR", tmp_path)
    monkeypatch.setattr(docker_manager, "ensure_image", lambda: None)
    monkeypatch.setattr(
        docker_manager,
        "run_bot_container",
        lambda container_name, bot_data_dir, api_port_external: type("C", (), {"id": "container-2"})(),
    )

    # Act
    await BotService(bot_repo, FakeApiKeysRepo()).start_bot(bot)  # type: ignore

    # Assert
    assert bot.status == "running"
    assert bot.error_message is None
