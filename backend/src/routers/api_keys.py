from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession 
from src.schemas.api_keys import ApiKeyListItem, ApiKeyCreate
from src.database import get_db
from src.core.dependencies import get_current_user  
from src.models.user import User
from src.services.api_keys_service import ApiKeyService
router = APIRouter(prefix="/api-keys", tags=["api-keys"])

# ── Эндпоинт ───────────────────────────────────────────────────────────────

@router.get("", response_model=list[ApiKeyListItem])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Список API-ключей текущего пользователя (только активные)."""
    return await ApiKeyService(db).get_list_api_keys(current_user)

@router.post("", response_model=ApiKeyListItem, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Сохранить новый API-ключ (секреты шифруются перед записью)."""
    return await ApiKeyService(db).create_api_key(current_user, payload)
 
 
@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Полное удаление ключа
    """
    await ApiKeyService(db).delete_api_key(current_user, key_id)
