from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.models.user import User
from src.schemas.user import RegisterRequest, LoginRequest, TokenResponse, UserPublic
from src.core.security import hash_password, verify_password, create_token
from src.core.dependencies import get_current_user
from src.repositories.user_repository import UserRepository
router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if await UserRepository(db).email_exists(body.email):
        raise HTTPException(status_code=400, detail="Email уже занят")


    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return TokenResponse(
        access_token=create_token(user.id),
        user_id=user.id,
        username=user.username,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await UserRepository(db).get_user(body.email)

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")

    return TokenResponse(
        access_token=create_token(user.id),
        user_id=user.id,
        username=user.username,
    )


@router.get("/me", response_model=UserPublic)
async def me(current_user: User = Depends(get_current_user)):
    return current_user