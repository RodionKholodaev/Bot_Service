import pytest_asyncio
import sentry_sdk
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from src.main import app

# src.main при импорте поднимает sentry_sdk с боевым DSN, поэтому любой logger.critical
# из тестов улетал бы в Glitchtip как настоящий инцидент. Пустой DSN гасит клиент —
# на код это не влияет, sentry_sdk просто становится no-op.
sentry_sdk.init(dsn="")
from src.database import get_db
from src.database import Base
from sqlalchemy import delete
from src.models.user import User

DATABASE_URL = "sqlite+aiosqlite:///./test.db" # адрес тестовой бд


engine = create_async_engine(
    DATABASE_URL,
    future=True,
    echo=False,
)

TestingSessionLocal = async_sessionmaker( # тестовая фабрика сессий
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def override_get_db(): # зависимость для получения тестовой сессии
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
        await conn.run_sync(Base.metadata.drop_all) # удаляем старые таблицы
        await conn.run_sync(Base.metadata.create_all) # создаем новые

    yield # тут прогоняются все тесты

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all) # после всех тестов удаляем все данные


@pytest_asyncio.fixture
async def db_session(): # фикстура из зависимости override_get_db
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


# очищает таблицу User перед каждым тестом
@pytest_asyncio.fixture(autouse=True)
async def clear_database():
    async with TestingSessionLocal() as session:
        await session.execute(delete(User))
        await session.commit()