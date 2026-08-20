"""Генерация config.json для каждого бота из шаблона."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "config.template.json"


async def generate_config(
    pair: str,
    api_port_inside_container: int,
    jwt_secret: str,
    ws_token: str,
    api_username: str,
    api_password: str,
    exchange_key: str,
    exchange_secret: str,
    stake_amount: float,
    tradable_balance_ratio: float,
    user_id: int,
    dry_run: bool = True,
) -> dict:
    """
    Возвращает готовый dict с конфигом для одного бота.

    api_port_inside_container — порт, который freqtrade слушает ВНУТРИ контейнера.
    Снаружи мы пробросим его на bot.api_port из БД через docker port mapping.
    Внутри пусть всегда будет 8080 (как в шаблоне) — это просто удобство.
    """
    logger.info(
        "Generating bot config",
        extra={
            "pair": pair,
            "user_id": user_id,
            "dry_run": dry_run,
            "api_port": api_port_inside_container,
        },
    )

    # Small local template read on the rare bot-creation path — not worth asyncio.to_thread.
    with open(TEMPLATE_PATH, encoding="utf-8") as f:  # noqa: ASYNC230
        config = json.load(f)

    config["stake_amount"] = stake_amount
    config["tradable_balance_ratio"] = tradable_balance_ratio
    config["exchange"]["pair_whitelist"] = [pair]
    config["dry_run"] = dry_run
    config["exchange"]["key"] = exchange_key
    config["exchange"]["secret"] = exchange_secret
    config["api_server"]["listen_port"] = api_port_inside_container
    config["api_server"]["jwt_secret_key"] = jwt_secret
    config["api_server"]["ws_token"] = ws_token
    config["api_server"]["username"] = api_username
    config["api_server"]["password"] = api_password

    config["telegram"]["enabled"] = False

    logger.info(
        "Bot config generated successfully",
        extra={"pair": pair, "user_id": user_id, "dry_run": dry_run},
    )
    return config


def write_config(config: dict, target_path: Path) -> None:
    """Сериализует и пишет config.json на диск."""
    logger.info(
        "Writing bot config to disk",
        extra={"target_path": str(target_path)},
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    logger.info(
        "Bot config written successfully",
        extra={"target_path": str(target_path)},
    )
