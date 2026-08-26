"""Интеграционные тесты /auth — реальное приложение поверх временной SQLite.

Помимо самой регистрации/входа тут проверяется, что обязательные юридические
галочки нельзя обойти запросом мимо формы и что принятые согласия реально
доезжают до таблицы consent_log.
"""

import pytest
from sqlalchemy import select, update

from src.config import settings
from src.core.legal import DOC_CROSS_BORDER, DOC_MARKETING, DOC_PDN_CONSENT, DOC_TERMS, TERMS_VERSION
from src.core.security import create_token
from src.models.consent_log import ConsentLog
from src.models.user import User


def register_payload(**overrides) -> dict:
    """Валидное тело регистрации со всеми обязательными согласиями."""
    payload = {
        "username": "rodion",
        "email": "test@test.com",
        "password": "12345678",
        "accept_terms": True,
        "accept_pdn": True,
        "accept_cross_border": True,
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_register_success(client):
    response = await client.post(
        "/auth/register",
        json=register_payload(),
    )

    assert response.status_code == 201

    data = response.json()

    assert "access_token" in data
    assert data["username"] == "rodion"
    assert data["user_id"] is not None


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    # первый пользователь
    await client.post(
        "/auth/register",
        json=register_payload(),
    )

    # повторная регистрация
    response = await client.post(
        "/auth/register",
        json=register_payload(),
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_register_without_consents_is_rejected(client):
    """Клиент без галочек (или вовсе без этих полей) получает 400, а не аккаунт."""
    response = await client.post(
        "/auth/register",
        json={
            "username": "rodion",
            "email": "test@test.com",
            "password": "12345678",
        },
    )

    assert response.status_code == 400
    assert "Пользовательское соглашение" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_without_cross_border_consent_is_rejected(client):
    """Согласие на трансграничную передачу — отдельная галочка, её недостаточно закрыть общей."""
    response = await client.post(
        "/auth/register",
        json=register_payload(accept_cross_border=False),
    )

    assert response.status_code == 400
    assert "трансграничную передачу" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_writes_consent_log(client, db_session):
    """Принятые документы попадают в consent_log — это и есть доказательство для проверки РКН."""
    response = await client.post(
        "/auth/register",
        json=register_payload(),
    )
    user_id = response.json()["user_id"]

    rows = (await db_session.execute(select(ConsentLog).where(ConsentLog.user_id == user_id))).scalars().all()

    types = {row.document_type for row in rows}
    assert types == {DOC_TERMS, DOC_PDN_CONSENT, DOC_CROSS_BORDER}
    # рассылки не отмечали — необязательного согласия в логе быть не должно
    assert DOC_MARKETING not in types

    terms_row = next(row for row in rows if row.document_type == DOC_TERMS)
    assert terms_row.document_version == TERMS_VERSION
    assert terms_row.accepted_at is not None


@pytest.mark.asyncio
async def test_marketing_consent_is_written_when_checked(client, db_session):
    response = await client.post(
        "/auth/register",
        json=register_payload(accept_marketing=True),
    )
    user_id = response.json()["user_id"]

    rows = (
        (
            await db_session.execute(
                select(ConsentLog).where(
                    ConsentLog.user_id == user_id,
                    ConsentLog.document_type == DOC_MARKETING,
                )
            )
        )
        .scalars()
        .all()
    )

    assert len(rows) == 1


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post(
        "/auth/register",
        json=register_payload(),
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
    await client.post(
        "/auth/register",
        json=register_payload(),
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
    register_response = await client.post(
        "/auth/register",
        json=register_payload(),
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
        json=register_payload(),
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
        json=register_payload(),
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
