import pytest
from src.services.auth_service import AuthService
from src.schemas.user import RegisterRequest, LoginRequest
from tests.fakes.test_user_repository import FakeUserRepository
from src.core.exceptions import UnauthorizedError  

@pytest.mark.asyncio
async def test_register():
    repo = FakeUserRepository()
    service = AuthService(repo) #type:ignore

    body = RegisterRequest(
        username="test",
        email="test@test.com",
        password="12345678"
    )

    result = await service.register(body)

    assert result.user_id == 1
    assert result.username == "test"

@pytest.mark.asyncio
async def test_login():
    repo = FakeUserRepository()
    service = AuthService(repo) #type: ignore
    body = LoginRequest(
        email="thereisnoemaillikethat@mail.ru",
        password="qwerty"
    )

    with pytest.raises(UnauthorizedError) as exc_info:
        result = await service.login(body)
    
    assert str(exc_info.value) == "Неверный email или пароль"