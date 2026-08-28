"""
Интеграционный тест GET /bots/presets — настоящее приложение поверх временной SQLite.

Проверяет ровно то, чего не видно из юнит-тестов: что запрос вообще доезжает до
обработчика. Путь "/bots/presets" объявлен рядом с "/bots/{bot_id}", и стоит им
поменяться местами — "presets" уедет туда как id бота, форма создания останется без
готовых стратегий, а юнит-тесты этого не заметят.
"""

import pytest

from src.services.strategy_presets import PRESETS


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
async def test_presets_endpoint_returns_all_presets(client):
    # Arrange
    token = await register_and_get_token(client)

    # Act
    response = await client.get("/bots/presets", headers={"Authorization": f"Bearer {token}"})

    # Assert
    assert response.status_code == 200

    data = response.json()
    assert {item["key"] for item in data} == set(PRESETS)

    moderate = next(item for item in data if item["key"] == "moderate")
    # форма заполняет по этому ответу и условия входа, и TP/SL — своих чисел у неё нет
    assert moderate["take_profit_percent"] == PRESETS["moderate"]["take_profit_percent"]
    assert moderate["stop_loss_percent"] == PRESETS["moderate"]["stop_loss_percent"]
    assert moderate["long_filters"] == PRESETS["moderate"]["long_filters"]
    assert moderate["name"] == "Умеренный"


@pytest.mark.asyncio
async def test_presets_endpoint_requires_authorization(client):
    # Arrange / Act
    response = await client.get("/bots/presets")

    # Assert
    assert response.status_code == 401
