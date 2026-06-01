from src.repositories.user_repository import UserRepository
from fastapi import HTTPException
from src.models.user import User
from src.core.security import hash_password, verify_password
from src.schemas.user import TokenResponse
from src.core.security import create_token
class AuthService:
    def __init__(self, db):
        self.repo = UserRepository(db)
    
    async def register(self, body):
        if await self.repo.email_exists(body.email):
            raise HTTPException(status_code=400, detail="Email уже занят")


        user = User(
            username=body.username,
            email=body.email,
            password_hash=hash_password(body.password),
        )
        await self.repo.create_user(user)

        return TokenResponse(
            access_token=create_token(user.id),
            user_id=user.id,
            username=user.username,
        )
    
    async def login(self, body):
        user = await self.repo.get_user(body.email)
        if not user or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Неверный email или пароль")
        

        return TokenResponse(
            access_token=create_token(user.id),
            user_id=user.id,
            username=user.username,
        )

