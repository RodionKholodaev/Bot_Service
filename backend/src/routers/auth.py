from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_db
from src.models.user import User
from src.schemas.user import RegisterRequest, LoginRequest, TokenResponse, UserPublic
from src.core.dependencies import get_current_user, get_user_repo
from src.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest, 
    db: AsyncSession = Depends(get_db),
    repo = Depends(get_user_repo),
):
    return await AuthService(db, repo).register(body)

@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, 
    db: AsyncSession = Depends(get_db),
    repo = Depends(get_user_repo),
):
    return await AuthService(db, repo).login(body)

@router.get("/me", response_model=UserPublic)
async def me(current_user: User = Depends(get_current_user)):
    return current_user