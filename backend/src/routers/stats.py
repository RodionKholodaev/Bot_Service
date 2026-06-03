# src/routers/stats.py

from typing import Optional, Literal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.dependencies import get_bot_repo, get_trade_repo
from src.database import get_db
from src.core.dependencies import get_current_user
from src.models.user import User
from src.models.bot import Bot
from src.schemas.stats import PortfolioStats, BotStats, HomeStats
from src.services.stats_service import StatsService
from fastapi import HTTPException
from src.repositories.bot_repository import BotRepository
from src.repositories.trade_repository import TradeRepository

router = APIRouter(prefix="/stats", tags=["stats"])

# Маппинг периодов в дни
PERIOD_MAP: dict[str, Optional[int]] = {
    "1D": 1,
    "1W": 7,
    "1M": 30,
    "all": None,
}


@router.get("/home", response_model=HomeStats)
async def home_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    bot_repo: BotRepository = Depends(get_bot_repo),
    trade_repo: TradeRepository = Depends(get_trade_repo)
):
    """
    Данные для главной страницы:
    баланс, суммарный профит, кол-во ботов, последние сделки.
    """
    return await StatsService(bot_repo, trade_repo).get_home_stats(current_user)


@router.get("/portfolio", response_model=PortfolioStats)
async def portfolio_stats(
    period: Literal["1D", "1W", "1M", "all"] = Query(default="1W"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    bot_repo: BotRepository = Depends(get_bot_repo),
    trade_repo: TradeRepository = Depends(get_trade_repo)
):
    """
    Агрегированная статистика по всем ботам пользователя.
    Используется на странице статистики при выборе «Все боты».
    """
    period_days = PERIOD_MAP[period]
    return await StatsService(bot_repo, trade_repo).get_portfolio_stats(current_user, period_days)


@router.get("/bots/{bot_id}", response_model=BotStats)
async def bot_stats(
    bot_id: str,
    period: Literal["1D", "1W", "1M", "all"] = Query(default="1W"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    bot_repo: BotRepository = Depends(get_bot_repo),
    trade_repo: TradeRepository = Depends(get_trade_repo)
):
    """
    Детальная статистика по одному боту.
    Используется на странице статистики при выборе конкретного бота.
    """
    bot: Optional[Bot] = await BotRepository(db).get_bot_by_id(bot_id)
    if not bot or bot.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Bot not found")

    period_days = PERIOD_MAP[period]
    return await StatsService(bot_repo, trade_repo).get_bot_stats(bot, period_days)