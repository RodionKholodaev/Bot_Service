# src/services/balance_guard.py
"""
Порог сервисного баланса: ниже settings.MIN_SERVICE_BALANCE_RUB боевой бот не
создаётся, не запускается, а уже запущенный останавливается.

Это именно порог, а не пол: комиссия за закрытую сделку списывается полностью
(см. CommissionService.process_commission), поэтому баланс может оказаться ниже порога
и даже отрицательным — недоплата остаётся долгом на балансе и гасится ближайшим
пополнением. Проверка здесь решает только один вопрос: пускать ли пользователя дальше
торговать в долг.

Dry-run боты не ограничиваются: за них комиссия не берётся вообще, сервису они ничего
не стоят.

Почему отдельный модуль, а не проверка внутри CommissionService: тот считает одну
сделку над переданной сессией и ничего не коммитит и не знает про docker. Остановка
контейнеров — побочный эффект совсем другого уровня, и держать её там значило бы
тащить docker в его юнит-тесты.
"""

import logging
from collections import defaultdict
from collections.abc import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.bot import Bot
from src.models.user import User
from src.repositories.bot_repository import BotRepository
from src.repositories.user_repository import UserRepository
from src.services import docker_manager

logger = logging.getLogger(__name__)


def is_balance_sufficient(user: User) -> bool:
    """Хватает ли баланса, чтобы боевой бот работал. Ровно порог — уже достаточно."""
    return user.service_balance >= settings.MIN_SERVICE_BALANCE_RUB


def _threshold() -> str:
    """Порог для текста сообщения: 100.0 -> "100"."""
    return f"{settings.MIN_SERVICE_BALANCE_RUB:g}"


def stopped_message() -> str:
    """Текст в Bot.error_message остановленного бота — его видит пользователь на /home."""
    return f"Баланс сервиса ниже {_threshold()} ₽ — бот остановлен. Пополните баланс, чтобы запустить его снова."


def cannot_create_message() -> str:
    return f"Баланс сервиса меньше {_threshold()} ₽. Пополните баланс, чтобы создать бота."


def cannot_start_message() -> str:
    return f"Баланс сервиса меньше {_threshold()} ₽. Пополните баланс, чтобы запустить бота."


async def stop_bots_for_low_balance(db: AsyncSession, user: User, bots: Iterable[Bot]) -> list[Bot]:
    """
    Останавливает боевых работающих ботов пользователя и возвращает список остановленных.

    Статус "stopped", а не "error": бот не сломался, его выключил сервис, и после
    пополнения пользователь запустит его обычной кнопкой. По той же причине здесь нет
    logger.critical — будить разработчика телеграм-алертом (см. core/telegram_alerts.py)
    тут не за чем.
    """
    to_stop = [bot for bot in bots if bot.status == "running" and not bot.dry_run]
    if not to_stop:
        return []

    bot_repo = BotRepository(db)
    message = stopped_message()
    for bot in to_stop:
        await bot_repo.change_bot_status("stopped", bot)
        await bot_repo.add_error_message(message, bot)

    # Коммитим до остановки контейнеров: если docker откажет, статус всё равно должен
    # остаться в БД, иначе воркер будет пытаться остановить этих ботов каждый цикл.
    await db.commit()

    logger.warning(
        "Bots stopped: service balance below minimum",
        extra={
            "user_id": user.id,
            "service_balance": user.service_balance,
            "min_balance": settings.MIN_SERVICE_BALANCE_RUB,
            "stopped_bots": [bot.id for bot in to_stop],
        },
    )

    for bot in to_stop:
        if not bot.container_id:
            continue
        try:
            docker_manager.stop_container(bot.container_id)
        except Exception:
            logger.exception(
                "Failed to stop container of a bot with low balance",
                extra={"bot_id": bot.id, "container_id": bot.container_id},
            )

    return to_stop


async def stop_bots_of_low_balance_users(db: AsyncSession, bots: Iterable[Bot]) -> list[Bot]:
    """
    Проверяет баланс владельцев переданных работающих ботов и останавливает тех, кому
    торговать уже нельзя. Возвращает ботов, с которыми можно работать дальше.

    Возвращаемый список важен: остановленного бота нельзя оставлять в текущем цикле
    воркера — ping в убитый контейнер не пройдёт, и через MAX_PING_MISSES бот уедет в
    статус "error" с критическим алертом, хотя его выключили штатно.
    """
    by_user: dict[int, list[Bot]] = defaultdict(list)
    for bot in bots:
        by_user[bot.user_id].append(bot)

    user_repo = UserRepository(db)
    allowed: list[Bot] = []

    for user_id, user_bots in by_user.items():
        user = await user_repo.get_user_by_id(user_id)
        # Пользователя нет (осиротевшие боты — внешние ключи в SQLite не работают):
        # решать за него нечего, оставляем боты воркеру как раньше.
        if user is None or is_balance_sufficient(user):
            allowed.extend(user_bots)
            continue

        stopped_ids = {bot.id for bot in await stop_bots_for_low_balance(db, user, user_bots)}
        allowed.extend(bot for bot in user_bots if bot.id not in stopped_ids)

    return allowed
