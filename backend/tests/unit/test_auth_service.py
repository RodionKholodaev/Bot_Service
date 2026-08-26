"""Юнит-тесты AuthService: регистрация, вход и запись юридических согласий.

БД тут нет — оба репозитория подменены фейками (tests/fakes/), поэтому проверки
касаются только логики сервиса: какие галочки обязательны, что попадает в
consent_log и с какой версией документа.
"""

import pytest

from src.core.exceptions import BadRequestError, ConflictError, UnauthorizedError
from src.core.legal import (
    DOC_CROSS_BORDER,
    DOC_MARKETING,
    DOC_PDN_CONSENT,
    DOC_TERMS,
    MARKETING_CONSENT_VERSION,
    PDN_CONSENT_VERSION,
    TERMS_VERSION,
)
from src.core.security import hash_password
from src.models.user import User
from src.schemas.user import LoginRequest, RegisterRequest
from src.services.auth_service import AuthService
from tests.fakes.test_consent_repository import FakeConsentRepository
from tests.fakes.test_user_repository import FakeUserRepository


def make_register_body(**overrides) -> RegisterRequest:
    """Тело регистрации со всеми обязательными галочками. Нужную снимаем через overrides."""
    fields = {
        "username": "test",
        "email": "test@test.com",
        "password": "12345678",
        "accept_terms": True,
        "accept_pdn": True,
        "accept_cross_border": True,
        "accept_marketing": False,
    }
    fields.update(overrides)
    return RegisterRequest(**fields)


def make_service() -> tuple[AuthService, FakeUserRepository, FakeConsentRepository]:
    """Сервис на фейковых репозиториях + сами репозитории для проверок."""
    repo = FakeUserRepository()
    consent_repo = FakeConsentRepository()
    return AuthService(repo, consent_repo), repo, consent_repo  # type:ignore


@pytest.mark.asyncio
async def test_register_success():
    # Arrange
    service, repo, _ = make_service()
    body = make_register_body()

    # Act
    result = await service.register(body)
    user = await repo.get_user("test@test.com")

    # Assert
    assert result.user_id == 1
    assert result.username == "test"
    assert user is not None and user.password_hash != body.password


@pytest.mark.asyncio
async def test_register_email_conflict():
    # Arrange
    service, _, _ = make_service()
    body1 = make_register_body()
    body2 = make_register_body(username="test1", password="gfhjjkjkhjhm")

    # Act
    await service.register(body1)

    # Assert
    with pytest.raises(ConflictError):
        await service.register(body2)


@pytest.mark.asyncio
async def test_register_returns_token():
    # Arrange
    service, _, _ = make_service()

    # Act
    result = await service.register(make_register_body())

    # Assert
    assert result.access_token != ""


@pytest.mark.asyncio
async def test_register_without_terms_is_rejected():
    """Галочку «принимаю Пользовательское соглашение» проверяет бэкенд, а не только браузер."""
    # Arrange
    service, repo, _ = make_service()

    # Act / Assert
    with pytest.raises(BadRequestError) as exc_info:
        await service.register(make_register_body(accept_terms=False))

    assert "Пользовательское соглашение" in exc_info.value.detail
    assert await repo.get_user("test@test.com") is None  # аккаунт не создан


@pytest.mark.asyncio
async def test_register_without_pdn_consent_is_rejected():
    # Arrange
    service, repo, _ = make_service()

    # Act / Assert
    with pytest.raises(BadRequestError) as exc_info:
        await service.register(make_register_body(accept_pdn=False))

    assert "обработку персональных данных" in exc_info.value.detail
    assert await repo.get_user("test@test.com") is None


@pytest.mark.asyncio
async def test_register_without_cross_border_consent_is_rejected(monkeypatch):
    """Пока база вне РФ, трансграничная передача — отдельная обязательная галочка.

    Флаг выставляем руками, чтобы тест не зависел от текущего значения в
    legal.py; monkeypatch по модулю, который CROSS_BORDER_TRANSFER импортировал.
    """
    # Arrange
    monkeypatch.setattr("src.services.auth_service.CROSS_BORDER_TRANSFER", True)
    service, repo, _ = make_service()

    # Act / Assert
    with pytest.raises(BadRequestError) as exc_info:
        await service.register(make_register_body(accept_cross_border=False))

    assert "трансграничную передачу" in exc_info.value.detail
    assert await repo.get_user("test@test.com") is None


@pytest.mark.asyncio
async def test_cross_border_consent_not_required_when_data_stays_in_russia(monkeypatch):
    """Если база переедет в РФ, третья галочка перестаёт быть обязательной и не пишется в лог."""
    # Arrange
    monkeypatch.setattr("src.services.auth_service.CROSS_BORDER_TRANSFER", False)
    service, _, consent_repo = make_service()

    # Act
    await service.register(make_register_body(accept_cross_border=False))

    # Assert
    assert DOC_CROSS_BORDER not in consent_repo.types()


@pytest.mark.asyncio
async def test_register_writes_consents_with_document_versions(monkeypatch):
    """В consent_log уходит по строке на согласие — с версией из legal.py, а не из тела запроса."""
    # Arrange
    monkeypatch.setattr("src.services.auth_service.CROSS_BORDER_TRANSFER", True)
    service, _, consent_repo = make_service()

    # Act
    result = await service.register(make_register_body(), client_ip="203.0.113.7")

    # Assert
    assert consent_repo.types() == [DOC_TERMS, DOC_PDN_CONSENT, DOC_CROSS_BORDER]
    versions = {row["document_type"]: row["document_version"] for row in consent_repo.rows}
    assert versions[DOC_TERMS] == TERMS_VERSION
    assert versions[DOC_PDN_CONSENT] == PDN_CONSENT_VERSION
    # трансграничная передача — пункт того же документа, поэтому версия от Согласия на ПДн
    assert versions[DOC_CROSS_BORDER] == PDN_CONSENT_VERSION
    assert all(row["user_id"] == result.user_id for row in consent_repo.rows)
    assert all(row["ip_address"] == "203.0.113.7" for row in consent_repo.rows)


@pytest.mark.asyncio
async def test_marketing_consent_is_optional():
    """Без галочки на рассылки регистрация проходит, но строки о ней в логе нет."""
    # Arrange
    service, _, consent_repo = make_service()

    # Act
    result = await service.register(make_register_body(accept_marketing=False))

    # Assert
    assert result.user_id == 1
    assert DOC_MARKETING not in consent_repo.types()


@pytest.mark.asyncio
async def test_marketing_consent_is_logged_when_given():
    # Arrange
    service, _, consent_repo = make_service()

    # Act
    await service.register(make_register_body(accept_marketing=True))

    # Assert
    marketing = [row for row in consent_repo.rows if row["document_type"] == DOC_MARKETING]
    assert len(marketing) == 1
    assert marketing[0]["document_version"] == MARKETING_CONSENT_VERSION


@pytest.mark.asyncio
async def test_no_consents_written_when_email_is_taken():
    """Согласия пишутся только вместе с реально созданным аккаунтом."""
    # Arrange
    service, _, consent_repo = make_service()
    await service.register(make_register_body())
    rows_after_first = len(consent_repo.rows)

    # Act
    with pytest.raises(ConflictError):
        await service.register(make_register_body(username="test1"))

    # Assert
    assert len(consent_repo.rows) == rows_after_first


@pytest.mark.asyncio
async def test_login_wrong_password():
    # Arrange
    service, repo, _ = make_service()
    user = User(username="Rodion137", email="test@mail.ru", password_hash=hash_password("12345"))
    await repo.create_user(user)

    # Act / Assert
    body = LoginRequest(email="test@mail.ru", password="not12345")
    with pytest.raises(UnauthorizedError) as exc_info:
        await service.login(body)

    assert str(exc_info.value) == "Неверный email или пароль"


@pytest.mark.asyncio
async def test_login_user_not_found():
    # Arrange
    service, _, _ = make_service()
    body = LoginRequest(email="thereisnoemaillikethat@mail.ru", password="qwerty")

    # Act / Assert
    with pytest.raises(UnauthorizedError) as exc_info:
        await service.login(body)

    assert str(exc_info.value) == "Неверный email или пароль"


@pytest.mark.asyncio
async def test_login_success():
    # Arrange
    service, repo, _ = make_service()
    user = User(username="Rodion137", email="test@mail.ru", password_hash=hash_password("12345"))
    await repo.create_user(user)

    # Act
    body = LoginRequest(email="test@mail.ru", password="12345")
    result = await service.login(body)

    # Assert
    assert result.username == user.username
    assert result.user_id == user.id
    assert result.access_token != ""
