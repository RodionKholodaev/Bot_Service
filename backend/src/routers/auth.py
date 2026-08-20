from fastapi import APIRouter, Depends, status

from src.core.dependencies import get_current_user, get_user_repo
from src.models.user import User
from src.schemas.user import LoginRequest, RegisterRequest, TokenResponse, UserPublic
from src.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    repo=Depends(get_user_repo),
):
    return await AuthService(repo).register(body)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    repo=Depends(get_user_repo),
):
    return await AuthService(repo).login(body)


@router.get("/me", response_model=UserPublic)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
