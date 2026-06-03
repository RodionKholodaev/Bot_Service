import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)

from src.main import app
from src.database import get_db
from src.database import Base
from sqlalchemy import delete
from src.models.user import User

DATABASE_URL = "sqlite+aiosqlite:///./test.db"


engine = create_async_engine(
    DATABASE_URL,
    future=True,
    echo=False,
)

TestingSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_database():
    """
    Создание таблиц один раз перед тестами.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac



@pytest_asyncio.fixture(autouse=True)
async def clear_database():
    async with TestingSessionLocal() as session:
        await session.execute(delete(User))
        await session.commit()