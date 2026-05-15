from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession 

from src.schemas.api_keys import ApiKeyListItem, ApiKeyCreate
from src.database import get_db
from src.models.exchange_api_key import ExchangeApiKey
from src.core.dependencies import get_current_user  
from src.models.user import User
from src.repositories.api_keys_repository import ApiKeysRepository
from src.core.crypto import encrypt

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

# ── Эндпоинт ───────────────────────────────────────────────────────────────

@router.get("", response_model=list[ApiKeyListItem])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Список API-ключей текущего пользователя (только активные)."""
    keys = await ApiKeysRepository(db).user_active_keys(current_user.id)
    if keys is None: keys = []
    return [
        ApiKeyListItem(
            id=key.id,
            name=key.label,
            exchange=key.exchange,
            is_active=key.is_active,
            created_at= key.created_at
        )
        for key in keys
    ]

@router.post("", response_model=ApiKeyListItem, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Сохранить новый API-ключ (секреты шифруются перед записью)."""
    key = await ApiKeysRepository(db).add_api_key(current_user.id, payload)
    return ApiKeyListItem(
        id=key.id,
        name=key.label,
        exchange=key.exchange,
        is_active=key.is_active,
        created_at=key.created_at,
    )
 
 
@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Полное удаление ключа
    """
    key = await ApiKeysRepository(db).delete_key(current_user.id, key_id)
