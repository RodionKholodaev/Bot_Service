import pytest
from src.services.auth_service import AuthService
from src.schemas.user import RegisterRequest
from tests.fakes.test_user_repository import FakeUserRepository


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