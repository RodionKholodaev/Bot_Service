import pytest
from sqlalchemy import update

from src.config import settings
from src.core.security import create_token
from src.models.user import User


@pytest.mark.asyncio
async def test_register_success(client):
    payload = {
        "username": "rodion",
        "email": "test@test.com",
        "password": "12345678",
    }

    response = await client.post(
        "/auth/register",
        json=payload,
    )

    assert response.status_code == 201

    data = response.json()

    assert "access_token" in data
    assert data["username"] == "rodion"
    assert data["user_id"] is not None


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {
        "username": "rodion",
        "email": "test@test.com",
        "password": "12345678",
    }

    # первый пользователь
    await client.post(
        "/auth/register",
        json=payload,
    )

    # повторная регистрация
    response = await client.post(
        "/auth/register",
        json=payload,
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client):
    register_payload = {
        "username": "rodion",
        "email": "test@test.com",
        "password": "12345678",
    }

    await client.post(
        "/auth/register",
        json=register_payload,
    )

    login_payload = {
        "email": "test@test.com",
        "password": "12345678",
    }

    response = await client.post(
        "/auth/login",
        json=login_payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert "access_token" in data
    assert data["username"] == "rodion"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    register_payload = {
        "username": "rodion",
        "email": "test@test.com",
        "password": "12345678",
    }

    await client.post(
        "/auth/register",
        json=register_payload,
    )

    response = await client.post(
        "/auth/login",
        json={
            "email": "test@test.com",
            "password": "wrong_password",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_success(client):
    register_payload = {
        "username": "rodion",
        "email": "test@test.com",
        "password": "12345678",
    }

    register_response = await client.post(
        "/auth/register",
        json=register_payload,
    )

    token = register_response.json()["access_token"]

    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["email"] == "test@test.com"
    assert data["username"] == "rodion"


@pytest.mark.asyncio
async def test_me_unauthorized(client):
    response = await client.get("/auth/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_blocked_user_cannot_use_token(client, db_session):
    """Заблокированный аккаунт (is_active=False) не пускают даже с валидным токеном."""
    register_response = await client.post(
        "/auth/register",
        json={
            "username": "rodion",
            "email": "test@test.com",
            "password": "12345678",
        },
    )

    token = register_response.json()["access_token"]
    user_id = register_response.json()["user_id"]

    await db_session.execute(update(User).where(User.id == user_id).values(is_active=False))
    await db_session.commit()

    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_expired_token_is_rejected(client, monkeypatch):
    """Просроченный токен — это 401, а не вечный пропуск."""
    register_response = await client.post(
        "/auth/register",
        json={
            "username": "rodion",
            "email": "test@test.com",
            "password": "12345678",
        },
    )

    user_id = register_response.json()["user_id"]

    # отрицательный срок жизни — токен протух в момент выдачи
    monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", -1)
    expired_token = create_token(user_id)

    response = await client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
