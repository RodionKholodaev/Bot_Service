import logging

from src.core.exceptions import ConflictError, UnauthorizedError
from src.core.security import create_token, hash_password, verify_password
from src.models.user import User
from src.repositories.user_repository import UserRepository
from src.schemas.user import TokenResponse

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def register(self, body):
        if await self.repo.email_exists(body.email):
            logger.warning("Registration failed: email already exists", extra={"email": body.email})
            raise ConflictError("Email уже занят")

        user = User(
            username=body.username,
            email=body.email,
            password_hash=hash_password(body.password),
        )
        await self.repo.create_user(user)

        logger.info(
            "User registered",
            extra={
                "user_id": user.id,
                "email": user.email,
            },
        )

        return TokenResponse(
            access_token=create_token(user.id),
            user_id=user.id,
            username=user.username,
        )

    async def login(self, body):
        user = await self.repo.get_user(body.email)
        if not user or not verify_password(body.password, user.password_hash):
            logger.warning(
                "Login failed",
                extra={
                    "email": body.email,
                },
            )

            raise UnauthorizedError("Неверный email или пароль")

        logger.info(
            "User logged in",
            extra={
                "user_id": user.id,
            },
        )

        return TokenResponse(
            access_token=create_token(user.id),
            user_id=user.id,
            username=user.username,
        )
