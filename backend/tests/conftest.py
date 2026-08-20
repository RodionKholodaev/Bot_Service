import pytest_asyncio
import sentry_sdk
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.main import app

# src.main при импорте поднимает sentry_sdk с боевым DSN, поэтому любой logger.critical
# из тестов улетал бы в Glitchtip как настоящий инцидент. Пустой DSN гасит клиент —
# на код это не влияет, sentry_sdk просто становится no-op.
sentry_sdk.init(dsn="")
from src.config import settings

# Если в .env заданы TELEGRAM_FEEDBACK_*, интеграционные тесты слали бы настоящие
# сообщения в чат разработчика на каждый созданный отзыв. Гасим канал на время тестов —
# те тесты, которым нужна включённая отправка, включают её сами через monkeypatch.
settings.TELEGRAM_FEEDBACK_BOT_TOKEN = None
settings.TELEGRAM_FEEDBACK_CHAT_ID = None

from sqlalchemy import delete

from src.database import Base, get_db
from src.models.feedback import Feedback
from src.models.user import User

DATABASE_URL = "sqlite+aiosqlite:///./test.db"  # адрес тестовой бд


engine = create_async_engine(
    DATABASE_URL,
    future=True,
    echo=False,
)

TestingSessionLocal = async_sessionmaker(  # тестовая фабрика сессий
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def override_get_db():  # зависимость для получения тестовой сессии
    async with TestingSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# преопределение зависимостей
# говорим, когда нужна get_db используй override_get_db
# работает только на тестах, поскольку этот файл использует только pytest
app.dependency_overrides[get_db] = override_get_db

# фикстура - функция, которая преобразует данные или окружение для тестов


# говорим, что это фиктура, а не тест
# scope="session" - загружается один раз перед всеми тестами в сессии
# autouse=True - автоматически используется, без явного указания в параметрах теста
@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_database():
    """
    Создание таблиц один раз перед тестами.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)  # удаляем старые таблицы
        await conn.run_sync(Base.metadata.create_all)  # создаем новые

    yield  # тут прогоняются все тесты

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)  # после всех тестов удаляем все данные


@pytest_asyncio.fixture
async def db_session():  # фикстура из зависимости override_get_db
    async with TestingSessionLocal() as session:
        yield session


# создаем виртуальные http клиент для отправки запросов без сетевых вызовов
# то есть эта штука отпрвляет запрос сразу в app, без использования интернета и других технологий
@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac


# очищает таблицы перед каждым тестом
# SQLite переиспользует id после удаления строк, поэтому чистим и дочерние таблицы —
# иначе отзывы прошлого теста «прилипнут» к новому пользователю с тем же id
@pytest_asyncio.fixture(autouse=True)
async def clear_database():
    # Идём по всем таблицам метаданных, а не по списку моделей руками: новая модель
    # начнёт чиститься сама, без правки этой фикстуры.
    # reversed(sorted_tables) — порядок от зависимых к родительским (trades -> bots -> users),
    # иначе удаление users упёрлось бы во внешние ключи.
    async with TestingSessionLocal() as session:
        await session.execute(delete(Feedback))
        await session.execute(delete(User))
        await session.commit()
