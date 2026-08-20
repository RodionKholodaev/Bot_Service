# src/routers/stats.py

from typing import Literal

from fastapi import APIRouter, Depends, Query

from src.core.dependencies import get_bot_repo, get_current_user, get_trade_repo
from src.core.exceptions import NotFoundError
from src.models.bot import Bot
from src.models.user import User
from src.repositories.bot_repository import BotRepository
from src.repositories.trade_repository import TradeRepository
from src.schemas.stats import BotStats, HomeStats, PortfolioStats
from src.services.stats_service import StatsService

router = APIRouter(prefix="/stats", tags=["stats"])

# Маппинг периодов в дни
PERIOD_MAP: dict[str, int | None] = {
    "1D": 1,
    "1W": 7,
    "1M": 30,
    "all": None,
}


@router.get("/home", response_model=HomeStats)
async def home_stats(
    current_user: User = Depends(get_current_user),
    bot_repo: BotRepository = Depends(get_bot_repo),
    trade_repo: TradeRepository = Depends(get_trade_repo),
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
    bot_repo: BotRepository = Depends(get_bot_repo),
    trade_repo: TradeRepository = Depends(get_trade_repo),
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
    bot_repo: BotRepository = Depends(get_bot_repo),
    trade_repo: TradeRepository = Depends(get_trade_repo),
):
    """
    Детальная статистика по одному боту.
    Используется на странице статистики при выборе конкретного бота.
    """
    bot: Bot | None = await bot_repo.get_bot_by_id(bot_id)
    # чужой и архивированный бот выглядят одинаково — 404, а не 403:
    # по коду ответа нельзя узнать, существует ли бот с таким id
    if bot is None or bot.user_id != current_user.id or not bot.is_active:
        raise NotFoundError("Бот не найден")

    period_days = PERIOD_MAP[period]
    return await StatsService(bot_repo, trade_repo).get_bot_stats(bot, period_days)
