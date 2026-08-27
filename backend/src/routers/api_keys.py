from fastapi import APIRouter, Depends, status

from src.core.dependencies import get_api_key_repo, get_bot_repo, get_current_user
from src.models.user import User
from src.repositories.api_keys_repository import ApiKeysRepository
from src.repositories.bot_repository import BotRepository
from src.schemas.api_keys import ApiKeyBalance, ApiKeyCreate, ApiKeyListItem
from src.services.api_keys_service import ApiKeyService

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

# ── Эндпоинт ───────────────────────────────────────────────────────────────


@router.get("", response_model=list[ApiKeyListItem])
async def list_api_keys(
    current_user: User = Depends(get_current_user), repo: ApiKeysRepository = Depends(get_api_key_repo)
):
    """Список API-ключей текущего пользователя (только активные)."""
    return await ApiKeyService(repo).get_list_api_keys(current_user)


@router.post("", response_model=ApiKeyListItem, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    repo: ApiKeysRepository = Depends(get_api_key_repo),
):
    """Сохранить новый API-ключ (секреты шифруются перед записью)."""
    return await ApiKeyService(repo).create_api_key(current_user, payload)


@router.get("/{key_id}/balance", response_model=ApiKeyBalance)
async def get_api_key_balance(
    key_id: int,
    current_user: User = Depends(get_current_user),
    repo: ApiKeysRepository = Depends(get_api_key_repo),
    bot_repo: BotRepository = Depends(get_bot_repo),
):
    """
    Свободный капитал ключа: баланс на бирже минус депозиты его боевых ботов.

    Ходит на биржу (с коротким кэшем), поэтому вынесен в отдельный эндпоинт и не
    подмешан в список ключей — иначе открытие страницы настроек стоило бы по запросу
    к бирже на каждый ключ.
    """
    return await ApiKeyService(repo).get_key_balance(current_user, key_id, bot_repo)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: int, current_user: User = Depends(get_current_user), repo: ApiKeysRepository = Depends(get_api_key_repo)
):
    """
    Полное удаление ключа
    """
    await ApiKeyService(repo).delete_api_key(current_user, key_id)
