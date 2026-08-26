from fastapi import APIRouter, Depends, Request, status

from src.core.dependencies import get_consent_repo, get_current_user, get_user_repo
from src.models.user import User
from src.schemas.user import LoginRequest, RegisterRequest, TokenResponse, UserPublic
from src.services.auth_service import AuthService
from src.services.get_ip import get_ip

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: Request,
    body: RegisterRequest,
    repo=Depends(get_user_repo),
    consent_repo=Depends(get_consent_repo),
):
    # IP пишем в consent_log как необязательное доказательство согласия;
    # None (адрес не определился) — не повод отказывать в регистрации.
    client_ip = get_ip(request)
    return await AuthService(repo, consent_repo).register(
        body,
        client_ip=str(client_ip) if client_ip else None,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    repo=Depends(get_user_repo),
    consent_repo=Depends(get_consent_repo),
):
    return await AuthService(repo, consent_repo).login(body)


@router.get("/me", response_model=UserPublic)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
