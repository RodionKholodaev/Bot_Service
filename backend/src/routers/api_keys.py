from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession 
from src.schemas.api_keys import ApiKeyListItem, ApiKeyCreate
from src.database import get_db
from src.core.dependencies import get_current_user, get_api_key_repo 
from src.models.user import User
from src.services.api_keys_service import ApiKeyService
from src.repositories.api_keys_repository import ApiKeysRepository

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

# ── Эндпоинт ───────────────────────────────────────────────────────────────

@router.get("", response_model=list[ApiKeyListItem])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    repo: ApiKeysRepository = Depends(get_api_key_repo)
):
    """Список API-ключей текущего пользователя (только активные)."""
    return await ApiKeyService(db, repo).get_list_api_keys(current_user)

@router.post("", response_model=ApiKeyListItem, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    repo: ApiKeysRepository = Depends(get_api_key_repo)
):
    """Сохранить новый API-ключ (секреты шифруются перед записью)."""
    return await ApiKeyService(db, repo).create_api_key(current_user, payload)
 
 
@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    repo: ApiKeysRepository = Depends(get_api_key_repo)
):
    """
    Полное удаление ключа
    """
    await ApiKeyService(db, repo).delete_api_key(current_user, key_id)
