from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.dependencies import get_current_user
from src.database import get_db
from src.models.bot import Bot
from src.models.user import User
from src.schemas.bot import BotCreate, BotPublic
from src.services import bot_manager, docker_manager, freqtrade_client

router = APIRouter(prefix="/bots", tags=["Bots"])


# ── Хелперы ───────────────────────────────────────────────

def _get_user_bot(db: Session, bot_id: str, user: User) -> Bot:
    """Достаёт бота с проверкой, что он принадлежит текущему пользователю."""
    bot = db.get(Bot, bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Бот не найден")
    if bot.user_id != user.id:
        raise HTTPException(status_code=404, detail="Бот не найден")
    return bot


# ── Создание + автозапуск ─────────────────────────────────

@router.post("", response_model=BotPublic, status_code=status.HTTP_201_CREATED)
def create_bot(
    body: BotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Создать бота и сразу его запустить.
    На UI после успешного ответа делаем редирект на /home.
    """
    if body.strategy_preset == "custom":
        if body.direction in ("long", "both") and not body.entry_filters_long:
            raise HTTPException(
                status_code=400,
                detail="Для custom стратегии и направления long/both нужны entry_filters_long",
            )
        if body.direction in ("short", "both") and not body.entry_filters_short:
            raise HTTPException(
                status_code=400,
                detail="Для custom стратегии и направления short/both нужны entry_filters_short",
            )

    if body.stop_loss_enabled and body.stop_loss_percent is None:
        raise HTTPException(
            status_code=400,
            detail="Если stop_loss_enabled=true, нужен stop_loss_percent",
        )

    try:
        bot = bot_manager.create_bot_record(db=db, user_id=current_user.id, body=body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось создать бота: {e}")

    # Сразу запускаем. Если запуск упал — бот останется в БД со статусом 'error',
    # фронт это увидит и сможет потом удалить или перезапустить.
    bot = bot_manager.start_bot(db=db, bot=bot)

    return bot


# ── Список / детали ───────────────────────────────────────

@router.get("", response_model=list[BotPublic])
def list_bots(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bots = (
        db.query(Bot)
        .filter(Bot.user_id == current_user.id, Bot.is_active == True)
        .order_by(Bot.created_at.desc())
        .all()
    )
    return bots


@router.get("/{bot_id}", response_model=BotPublic)
def get_bot(
    bot_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_user_bot(db, bot_id, current_user)


# ── Старт / стоп / удаление ───────────────────────────────

@router.post("/{bot_id}/start", response_model=BotPublic)
def start_bot_endpoint(
    bot_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bot = _get_user_bot(db, bot_id, current_user)
    return bot_manager.start_bot(db=db, bot=bot)


@router.post("/{bot_id}/stop", response_model=BotPublic)
def stop_bot_endpoint(
    bot_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bot = _get_user_bot(db, bot_id, current_user)
    return bot_manager.stop_bot(db=db, bot=bot)


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bot_endpoint(
    bot_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bot = _get_user_bot(db, bot_id, current_user)
    bot_manager.delete_bot(db=db, bot=bot)
    return None


# ── Прокси к freqtrade ────────────────────────────────────

@router.get("/{bot_id}/freqtrade/status")
def freqtrade_status(
    bot_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bot = _get_user_bot(db, bot_id, current_user)
    data = freqtrade_client.get_status(bot)
    if data is None:
        raise HTTPException(status_code=503, detail="Бот недоступен")
    return data


# Эти не нужны больше:
# @router.get("/{bot_id}/freqtrade/profit")
# def freqtrade_profit(
#     bot_id: str,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user),
# ):
#     bot = _get_user_bot(db, bot_id, current_user)
#     data = freqtrade_client.get_profit(bot)
#     if data is None:
#         raise HTTPException(status_code=503, detail="Бот недоступен")
#     return data


# @router.get("/{bot_id}/freqtrade/trades")
# def freqtrade_trades(
#     bot_id: str,
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user),
# ):
#     bot = _get_user_bot(db, bot_id, current_user)
#     data = freqtrade_client.get_trades(bot)
#     if data is None:
#         raise HTTPException(status_code=503, detail="Бот недоступен")
#     return data


# ── Логи ──────────────────────────────────────────────────

@router.get("/{bot_id}/logs")
def get_logs(
    bot_id: str,
    tail: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    bot = _get_user_bot(db, bot_id, current_user)
    if not bot.container_id:
        return {"logs": ""}
    logs = docker_manager.get_container_logs(bot.container_id, tail=tail)
    return {"logs": logs}
