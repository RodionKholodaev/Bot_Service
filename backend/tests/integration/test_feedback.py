"""Интеграционные тесты POST /feedback — реальное приложение поверх временной SQLite."""

import pytest


async def register_and_get_token(client) -> str:
    """Регистрирует пользователя и возвращает его JWT."""
    response = await client.post(
        "/auth/register",
        json={
            "username": "rodion",
            "email": "test@test.com",
            "password": "12345678",
            "accept_terms": True,
            "accept_pdn": True,
            "accept_cross_border": True,
        },
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_create_feedback_success(client):
    # Arrange
    token = await register_and_get_token(client)

    payload = {
        "topic": "idea",
        "message": "Было бы здорово добавить пресет под скальпинг",
        "email": "answer@test.com",
        "rating": 5,
    }

    # Act
    response = await client.post(
        "/feedback",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    # Assert
    assert response.status_code == 201

    data = response.json()

    assert data["id"] is not None
    assert data["created_at"] is not None


@pytest.mark.asyncio
async def test_create_feedback_without_optional_fields(client):
    # Arrange
    # фронт шлёт null, если поля не заполнены
    token = await register_and_get_token(client)

    payload = {
        "topic": "other",
        "message": "Просто хотел сказать спасибо за сервис",
        "email": None,
        "rating": None,
    }

    # Act
    response = await client.post(
        "/feedback",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    # Assert
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_feedback_unauthorized(client):
    # Arrange
    payload = {
        "topic": "bug",
        "message": "Кнопка запуска бота не реагирует на клик",
        "email": None,
        "rating": None,
    }

    # Act
    response = await client.post("/feedback", json=payload)

    # Assert
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_feedback_message_too_short(client):
    # Arrange
    token = await register_and_get_token(client)

    payload = {
        "topic": "bug",
        "message": "коротко",  # меньше 10 символов
        "email": None,
        "rating": None,
    }

    # Act
    response = await client.post(
        "/feedback",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    # Assert
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_feedback_invalid_topic(client):
    # Arrange
    token = await register_and_get_token(client)

    payload = {
        "topic": "complaint",  # нет в списке тем
        "message": "Тема обращения не из списка допустимых",
        "email": None,
        "rating": None,
    }

    # Act
    response = await client.post(
        "/feedback",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    # Assert
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_feedback_rate_limited(client):
    # Arrange
    token = await register_and_get_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "topic": "idea",
        "message": "Ещё одна идея по улучшению сервиса",
        "email": None,
        "rating": None,
    }

    # Act
    # лимит — 5 отзывов в час, шестой должен упереться в него
    for _ in range(5):
        ok_response = await client.post("/feedback", json=payload, headers=headers)
        assert ok_response.status_code == 201

    response = await client.post("/feedback", json=payload, headers=headers)

    # Assert
    assert response.status_code == 429
    assert "detail" in response.json()
