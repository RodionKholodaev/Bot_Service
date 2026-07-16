import pytest
from src.services.auth_service import AuthService
from src.schemas.user import RegisterRequest, LoginRequest
from tests.fakes.test_user_repository import FakeUserRepository
from src.core.exceptions import UnauthorizedError, ConflictError
from src.models.user import User
from src.core.security import hash_password
@pytest.mark.asyncio
async def test_register_success():
    repo = FakeUserRepository()
    service = AuthService(repo) #type:ignore

    body = RegisterRequest(
        username="test",
        email="test@test.com",
        password="12345678"
    )

    result = await service.register(body)
    user = await repo.get_user("test@test.com")

    assert result.user_id == 1
    assert result.username == "test"
    assert user is not None and user.password_hash!=body.password

@pytest.mark.asyncio
async def test_register_email_conflict():
    repo = FakeUserRepository()
    service = AuthService(repo) #type:ignore

    body1 = RegisterRequest(
        username="test",
        email="test@test.com",
        password="12345678"
    )
    body2 = RegisterRequest(
        username="test1",
        email="test@test.com",
        password="gfhjjkjkhjhm"
    )

    await service.register(body1)

    with pytest.raises(ConflictError) as exc_info:
        await service.register(body2)

@pytest.mark.asyncio
async def test_register_returns_token():
    repo = FakeUserRepository()
    service = AuthService(repo) #type:ignore
    body = RegisterRequest(
        username="test",
        email="test@test.com",
        password="12345678"
    )

    result = await service.register(body)
    assert result.access_token != ""



@pytest.mark.asyncio
async def test_login_wrong_password():
    repo = FakeUserRepository()
    service = AuthService(repo) #type:ignore
    user = User(
        username="Rodion137",
        email="test@mail.ru",
        password_hash=hash_password("12345")
    )
    await repo.create_user(user)


    body = LoginRequest(
        email = "test@mail.ru",
        password="not12345"
    )
    with pytest.raises(UnauthorizedError) as exc_info:
        await service.login(body)

    assert str(exc_info.value) == "Неверный email или пароль"


@pytest.mark.asyncio
async def test_login_user_not_found():
    repo = FakeUserRepository()
    service = AuthService(repo) #type: ignore
    body = LoginRequest(
        email="thereisnoemaillikethat@mail.ru",
        password="qwerty"
    )

    with pytest.raises(UnauthorizedError) as exc_info:
        await service.login(body)
    
    assert str(exc_info.value) == "Неверный email или пароль"

@pytest.mark.asyncio
async def test_login_success():
    repo = FakeUserRepository()
    service = AuthService(repo) #type: ignore
    user = User(
        username="Rodion137",
        email="test@mail.ru",
        password_hash=hash_password("12345")
    )
    await repo.create_user(user)


    body = LoginRequest(
        email = "test@mail.ru",
        password="12345"
    )
    result = await service.login(body)

    assert result.username == user.username
    assert result.user_id == user.id
    assert result.access_token != ""

