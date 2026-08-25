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
    deposit: float,
    stake_ratio: float,
    user_id: int,
    dry_run: bool = True,
) -> dict:
    """
    Возвращает готовый dict с конфигом для одного бота.

    api_port_inside_container — порт, который freqtrade слушает ВНУТРИ контейнера.
    Снаружи мы пробросим его на bot.api_port из БД через docker port mapping.
    Внутри пусть всегда будет 8080 (как в шаблоне) — это просто удобство.

    deposit — весь капитал бота (Bot.stake_amount), stake_ratio — доля депозита на одну
    сделку (Bot.tradable_balance_ratio, 0.2 = 20%). Имена в БД остались от прежней
    трактовки, здесь они переименованы по смыслу.

    Раскладка по ключам freqtrade — единственное место, где это соответствие задаётся:
      - stake_amount     — размер ОДНОЙ сделки, отсюда deposit * stake_ratio;
      - dry_run_wallet   — кошелёк симуляции, равен депозиту (иначе бот торгует
                           дефолтной тысячей и может «потерять» больше депозита);
      - available_capital — сколько боту разрешено взять с реального счёта: без него
                           в live-режиме бот считал бы своим весь баланс биржи.
    available_capital перекрывает tradable_balance_ratio, поэтому второго в конфиге нет.
    """
    logger.info(
        "Generating bot config",
        extra={
            "pair": pair,
            "user_id": user_id,
            "dry_run": dry_run,
            "api_port": api_port_inside_container,
            "deposit": deposit,
            "stake_ratio": stake_ratio,
        },
    )

    # Small local template read on the rare bot-creation path — not worth asyncio.to_thread.
    with open(TEMPLATE_PATH, encoding="utf-8") as f:  # noqa: ASYNC230
        config = json.load(f)

    config["stake_amount"] = round(deposit * stake_ratio, 8)
    config["dry_run_wallet"] = deposit
    config["available_capital"] = deposit
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
