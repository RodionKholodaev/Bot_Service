import pytest

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
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["email"] == "test@test.com"
    assert data["username"] == "rodion"


@pytest.mark.asyncio
async def test_me_unauthorized(client):
    response = await client.get("/auth/me")

    assert response.status_code == 401