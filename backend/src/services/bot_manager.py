"""
BotManager — оркестратор всего жизненного цикла бота.

Связывает БД, генерацию файлов и Docker. Именно его дёргают роутеры.
Сами роутеры остаются тонкими: валидация → BotManager.* → ответ.
"""

import logging
import secrets
import shutil
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from src.config import settings
from src.models.bot import Bot
from src.schemas.bot import BotCreate
from src.services import docker_manager
from src.services.freqtrade_config import generate_config, write_config
from src.services.freqtrade_strategy import generate_strategy_file, write_strategy_file
from src.services.strategy_presets import resolve_filters

logger = logging.getLogger(__name__)


# ── Утилиты ───────────────────────────────────────────────

def _bot_dir(bot_id: str) -> Path:
    return settings.BOTS_DATA_DIR / bot_id


def _allocate_port(db: Session) -> int:
    """
    Выдаёт первый свободный порт из диапазона BOT_API_PORT_RANGE_START..END.
    Простая реализация: смотрим занятые порты в БД (среди живых ботов).
    Этого достаточно для MVP.
    """
    used = {row[0] for row in db.query(Bot.api_port).all()}
    for port in range(settings.BOT_API_PORT_RANGE_START, settings.BOT_API_PORT_RANGE_END + 1):
        if port not in used:
            return port
    raise RuntimeError("Свободные порты в диапазоне закончились")


def _build_take_profit(percent: float) -> dict:
    """Превращает 4 (процентов) в minimal_roi {"0": 0.04}."""
    return {"0": round(percent / 100.0, 6)}


def _build_stoploss(enabled: bool, percent: float | None) -> float:
    """
    Возвращает stoploss в формате freqtrade (отрицательное число от цены).
    Если SL выключен — кладём -0.99 (фактически отключено).
    """
    if not enabled or percent is None:
        return -0.99
    return -round(percent / 100.0, 6)


# ── Создание бота ────────────────────────────────────────

def create_bot_record(db: Session, user_id: int, body: BotCreate) -> Bot:
    """
    Создаёт запись о боте в БД + генерирует на диск config.json и стратегию.
    Контейнер ещё не запускает.
    """
    bot_id = str(uuid.uuid4())
    container_name = f"bot_{bot_id.replace('-', '')[:24]}"
    api_port = _allocate_port(db)

    long_filters, short_filters = resolve_filters(
        preset=body.strategy_preset,
        direction=body.direction,
        custom_long=[f.model_dump() for f in body.entry_filters_long]
        if body.entry_filters_long else None,
        custom_short=[f.model_dump() for f in body.entry_filters_short]
        if body.entry_filters_short else None,
    )

    take_profit = _build_take_profit(body.take_profit_percent)
    stop_loss = _build_stoploss(body.stop_loss_enabled, body.stop_loss_percent)

    api_username = "freqtrader"
    api_password = secrets.token_urlsafe(16)

    bot = Bot(
        id=bot_id,
        user_id=user_id,
        name=body.name,
        pair=body.pair,
        leverage=body.leverage,
        direction=body.direction,
        strategy_preset=body.strategy_preset,
        entry_filters_long=long_filters,
        entry_filters_short=short_filters,
        take_profit=take_profit,
        stop_loss=stop_loss,
        trailing_stop=False,
        trailing_config=None,
        dry_run=body.dry_run,
        status="created",
        container_name=container_name,
        api_port=api_port,
        api_username=api_username,
        api_password=api_password,
    )

    db.add(bot)
    db.commit()
    db.refresh(bot)

    _materialize_files(bot)

    return bot


def _materialize_files(bot: Bot) -> None:
    """Создаёт папку бота, кладёт config.json и файл стратегии."""
    bot_dir = _bot_dir(bot.id)
    bot_dir.mkdir(parents=True, exist_ok=True)
    (bot_dir / "user_data" / "strategies").mkdir(parents=True, exist_ok=True)
    (bot_dir / "user_data" / "logs").mkdir(parents=True, exist_ok=True)
    (bot_dir / "user_data" / "data").mkdir(parents=True, exist_ok=True)

    cfg = generate_config(
        pair=bot.pair,
        api_port_inside_container=docker_manager.INTERNAL_API_PORT,
        jwt_secret=secrets.token_hex(32),
        ws_token=secrets.token_urlsafe(24),
        api_username=bot.api_username,
        api_password=bot.api_password,
        dry_run=bot.dry_run,
    )
    write_config(cfg, bot_dir / "config.json")

    can_short = bot.direction in ("short", "both")
    strategy_code = generate_strategy_file(
        leverage=bot.leverage,
        can_short=can_short,
        entry_filters_long=list(bot.entry_filters_long or []),
        entry_filters_short=list(bot.entry_filters_short or []),
        take_profit=dict(bot.take_profit),
        stoploss=bot.stop_loss,
        trailing_stop=bot.trailing_stop,
    )
    write_strategy_file(
        strategy_code,
        bot_dir / "user_data" / "strategies" / "MultiFilterStrategy.py",
    )


# ── Запуск / остановка / удаление ─────────────────────────

def start_bot(db: Session, bot: Bot) -> Bot:
    """Запускает контейнер для уже созданного бота."""
    bot_dir = _bot_dir(bot.id)
    if not (bot_dir / "config.json").exists():
        _materialize_files(bot)

    bot.status = "starting"
    bot.error_message = None
    db.commit()

    try:
        docker_manager.ensure_image()
        container = docker_manager.run_bot_container(
            container_name=bot.container_name,
            bot_data_dir=bot_dir,
            api_port_external=bot.api_port,
        )
        bot.container_id = container.id
        bot.status = "running"
    except Exception as e:
        logger.exception("Не удалось запустить контейнер")
        bot.status = "error"
        bot.error_message = str(e)[:500]
    finally:
        db.commit()
        db.refresh(bot)

    return bot


def stop_bot(db: Session, bot: Bot) -> Bot:
    if bot.container_id:
        docker_manager.stop_container(bot.container_id)
    bot.status = "stopped"
    db.commit()
    db.refresh(bot)
    return bot


def delete_bot(db: Session, bot: Bot) -> None:
    if bot.container_id:
        docker_manager.remove_container(bot.container_id)

    bot_dir = _bot_dir(bot.id)
    if bot_dir.exists():
        try:
            shutil.rmtree(bot_dir)
        except Exception:
            logger.exception(f"Не удалось удалить папку бота {bot_dir}")

    db.delete(bot)
    db.commit()
