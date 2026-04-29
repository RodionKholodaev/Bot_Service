# src/routers/stats.py

from typing import Optional, Literal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.database import get_db
from src.core.dependencies import get_current_user
from src.models.user import User
from src.models.bot import Bot
from src.schemas.stats import PortfolioStats, BotStats, HomeStats
from src.services import stats_service
from fastapi import HTTPException

router = APIRouter(prefix="/stats", tags=["stats"])

# Маппинг периодов в дни
PERIOD_MAP: dict[str, Optional[int]] = {
    "1D": 1,
    "1W": 7,
    "1M": 30,
    "all": None,
}


@router.get("/home", response_model=HomeStats)
def home_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Данные для главной страницы:
    баланс, суммарный профит, кол-во ботов, последние сделки.
    """
    return stats_service.get_home_stats(db, current_user)


@router.get("/portfolio", response_model=PortfolioStats)
def portfolio_stats(
    period: Literal["1D", "1W", "1M", "all"] = Query(default="1W"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Агрегированная статистика по всем ботам пользователя.
    Используется на странице статистики при выборе «Все боты».
    """
    period_days = PERIOD_MAP[period]
    return stats_service.get_portfolio_stats(db, current_user, period_days)


@router.get("/bots/{bot_id}", response_model=BotStats)
def bot_stats(
    bot_id: str,
    period: Literal["1D", "1W", "1M", "all"] = Query(default="1W"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Детальная статистика по одному боту.
    Используется на странице статистики при выборе конкретного бота.
    """
    bot: Optional[Bot] = db.query(Bot).filter(Bot.id == bot_id).first()
    if not bot or bot.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Bot not found")

    period_days = PERIOD_MAP[period]
    return stats_service.get_bot_stats(db, bot, period_days)