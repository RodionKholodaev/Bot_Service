"""
Клиент к REST API одного бота freqtrade.

Используется для проксирования /status, /trades, /profit с твоего бэкенда —
чтобы фронт никогда не ходил во freqtrade напрямую.
"""

import logging

import httpx

from src.config import settings
from src.models.bot import Bot

logger = logging.getLogger(__name__)


def _base_url(bot: Bot) -> str:
    return f"http://{settings.BOT_API_HOST}:{bot.api_port}/api/v1"


def _auth(bot: Bot) -> tuple[str, str]:
    return (bot.api_username, bot.api_password)


def get_status(bot: Bot, timeout: float = 5.0) -> dict | list | None:
    """GET /api/v1/status — открытые сделки."""
    logger.info(
        "Fetching bot status",
        extra={"bot_id": bot.id, "endpoint": "/status"},
    )
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{_base_url(bot)}/status", auth=_auth(bot))
            r.raise_for_status()
            logger.info(
                "Bot status fetched successfully",
                extra={"bot_id": bot.id, "status_code": r.status_code},
            )
            return r.json()
    except Exception as e:
        logger.error(
            "Failed to fetch bot status",
            extra={"bot_id": bot.id, "error": str(e)},
        )
        return None


def get_profit(bot: Bot, timeout: float = 5.0) -> dict | None:
    """GET /api/v1/profit — суммарная статистика."""
    logger.info(
        "Fetching bot profit",
        extra={"bot_id": bot.id, "endpoint": "/profit"},
    )
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{_base_url(bot)}/profit", auth=_auth(bot))
            r.raise_for_status()
            logger.info(
                "Bot profit fetched successfully",
                extra={"bot_id": bot.id, "status_code": r.status_code},
            )
            return r.json()
    except Exception as e:
        logger.error(
            "Failed to fetch bot profit",
            extra={"bot_id": bot.id, "error": str(e)},
        )
        return None


def get_trades(bot: Bot, timeout: float = 5.0) -> dict | None:
    """GET /api/v1/trades — закрытые сделки."""
    logger.info(
        "Fetching bot trades",
        extra={"bot_id": bot.id, "endpoint": "/trades"},
    )
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{_base_url(bot)}/trades", auth=_auth(bot))
            r.raise_for_status()
            logger.info(
                "Bot trades fetched successfully",
                extra={"bot_id": bot.id, "status_code": r.status_code},
            )
            return r.json()
    except Exception as e:
        logger.error(
            "Failed to fetch bot trades",
            extra={"bot_id": bot.id, "error": str(e)},
        )
        return None


def ping(bot: Bot, timeout: float = 2.0) -> bool:
    """Проверка живости бота."""
    logger.debug(
        "Pinging bot",
        extra={"bot_id": bot.id, "endpoint": "/ping"},
    )
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{_base_url(bot)}/ping", auth=_auth(bot))
            alive = r.status_code == 200
            logger.debug(
                "Bot ping result",
                extra={"bot_id": bot.id, "alive": alive, "status_code": r.status_code},
            )
            return alive
    except Exception as e:
        logger.warning(
            "Bot ping failed",
            extra={"bot_id": bot.id, "error": str(e)},
        )
        return False
