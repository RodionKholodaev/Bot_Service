"""
Клиент к REST API одного бота freqtrade.

Используется для проксирования /status, /trades, /profit с твоего бэкенда —
чтобы фронт никогда не ходил во freqtrade напрямую.
"""

import httpx

from src.config import settings
from src.models.bot import Bot


def _base_url(bot: Bot) -> str:
    return f"http://{settings.BOT_API_HOST}:{bot.api_port}/api/v1"


def _auth(bot: Bot) -> tuple[str, str]:
    return (bot.api_username, bot.api_password)


def get_status(bot: Bot, timeout: float = 5.0) -> dict | list | None:
    """GET /api/v1/status — открытые сделки."""
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{_base_url(bot)}/status", auth=_auth(bot))
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


def get_profit(bot: Bot, timeout: float = 5.0) -> dict | None:
    """GET /api/v1/profit — суммарная статистика."""
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{_base_url(bot)}/profit", auth=_auth(bot))
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


def get_trades(bot: Bot, timeout: float = 5.0) -> dict | None:
    """GET /api/v1/trades — закрытые сделки."""
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{_base_url(bot)}/trades", auth=_auth(bot))
            r.raise_for_status()
            return r.json()
    except Exception:
        return None


def ping(bot: Bot, timeout: float = 2.0) -> bool:
    """Проверка живости бота."""
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{_base_url(bot)}/ping", auth=_auth(bot))
            return r.status_code == 200
    except Exception:
        return False
