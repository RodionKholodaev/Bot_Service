from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.dependencies import get_current_user, get_bot_repo, get_api_key_repo
from src.database import get_db
from src.models.user import User
from src.schemas.bot import BotCreate, BotPublic
from src.repositories.bot_repository import BotRepository
from src.services.bot_service import BotService
router = APIRouter(prefix="/bots", tags=["Bots"])





# ── Создание + автозапуск ─────────────────────────────────

@router.post("", response_model=BotPublic, status_code=status.HTTP_201_CREATED)
async def create_bot(
    body: BotCreate,
    current_user: User = Depends(get_current_user),
    bot_repo: BotRepository = Depends(get_bot_repo),
    api_keys_repo = Depends(get_api_key_repo),
):
    """
    Создать бота и сразу его запустить.
    """
    botservice = BotService(bot_repo, api_keys_repo)

    bot = await botservice.create_bot(current_user, body)

    bot = await botservice.start_bot(bot)

    return bot


# ── Список / детали ───────────────────────────────────────

@router.get("", response_model=list[BotPublic])
async def list_bots(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bots = await BotRepository(db).get_user_bots(current_user.id)
    return bots


@router.get("/{bot_id}", response_model=BotPublic)
async def get_bot(
    bot_id: str,
    current_user: User = Depends(get_current_user),
    bot_repo: BotRepository = Depends(get_bot_repo),
    api_keys_repo = Depends(get_api_key_repo),
):
    return await BotService(bot_repo, api_keys_repo).get_user_bot(bot_id, current_user)


# ── Старт / стоп / удаление ───────────────────────────────

@router.post("/{bot_id}/start", response_model=BotPublic)
async def start_bot_endpoint(
    bot_id: str,
    current_user: User = Depends(get_current_user),
    bot_repo: BotRepository = Depends(get_bot_repo),
    api_keys_repo = Depends(get_api_key_repo),
):
    botservice = BotService(bot_repo, api_keys_repo)
    bot = await botservice.get_user_bot(bot_id, current_user)
    return await botservice.start_bot(bot)


@router.post("/{bot_id}/stop", response_model=BotPublic)
async def stop_bot_endpoint(
    bot_id: str,
    current_user: User = Depends(get_current_user),
    bot_repo: BotRepository = Depends(get_bot_repo),
    api_keys_repo = Depends(get_api_key_repo),
):
    botservice = BotService(bot_repo, api_keys_repo)
    bot = await botservice.get_user_bot(bot_id, current_user)
    return await botservice.stop_bot(bot)


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bot_endpoint(
    bot_id: str,
    current_user: User = Depends(get_current_user),
    bot_repo: BotRepository = Depends(get_bot_repo),
    api_keys_repo = Depends(get_api_key_repo),
):
    botservice = BotService(bot_repo, api_keys_repo)
    bot = await botservice.get_user_bot(bot_id, current_user)
    await botservice.delete_bot(bot)


# ── Прокси к freqtrade ────────────────────────────────────

@router.get("/{bot_id}/freqtrade/status")
async def freqtrade_status(
    bot_id: str,
    current_user: User = Depends(get_current_user),
    bot_repo: BotRepository = Depends(get_bot_repo),
    api_keys_repo = Depends(get_api_key_repo),
):
    bot = await BotService(bot_repo, api_keys_repo).get_user_bot(bot_id, current_user)
    data = BotService.freqtrade_status(bot)

    return data


# ── Логи ──────────────────────────────────────────────────

@router.get("/{bot_id}/logs")
async def get_logs(
    bot_id: str,
    tail: int = 200,
    current_user: User = Depends(get_current_user),
    bot_repo: BotRepository = Depends(get_bot_repo),
    api_keys_repo = Depends(get_api_key_repo),
):
    bot = await BotService(bot_repo, api_keys_repo).get_user_bot(bot_id, current_user)

    return BotService.get_logs(bot, tail)
