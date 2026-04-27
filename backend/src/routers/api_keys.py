from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.schemas.api_keys import ApiKeyListItem, ApiKeyCreate
from src.database import get_db
from src.models.exchange_api_key import ExchangeApiKey
from src.core.dependencies import get_current_user  
from src.models.user import User

from src.core.crypto import encrypt

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

# ── Эндпоинт ───────────────────────────────────────────────────────────────

@router.get("", response_model=list[ApiKeyListItem])
def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Список API-ключей текущего пользователя (только активные)."""
    keys = (
        db.query(ExchangeApiKey)
        .filter(
            ExchangeApiKey.user_id == current_user.id,
            ExchangeApiKey.is_active == True,
        )
        .order_by(ExchangeApiKey.created_at.desc())
        .all()
    )
    # Маппим label → name для фронта
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
def create_api_key(
    payload: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Сохранить новый API-ключ (секреты шифруются перед записью)."""
    key = ExchangeApiKey(
        user_id=current_user.id,
        exchange=payload.exchange,
        label=payload.name,
        api_key_encrypted=encrypt(payload.api_key),
        api_secret_encrypted=encrypt(payload.api_secret),
        is_active=True,
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return ApiKeyListItem(
        id=key.id,
        name=key.label,
        exchange=key.exchange,
        is_active=key.is_active,
        created_at=key.created_at,
    )
 
 
@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Мягкое удаление: ставим is_active=False.
    Ключ остаётся в БД для аудита и на случай активных ботов.
    """
    key = (
        db.query(ExchangeApiKey)
        .filter(
            ExchangeApiKey.id == key_id,
            ExchangeApiKey.user_id == current_user.id,
        )
        .first()
    )
    if key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API-ключ не найден",
        )
    key.is_active = False
    db.commit()