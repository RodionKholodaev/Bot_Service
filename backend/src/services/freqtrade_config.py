"""Генерация config.json для каждого бота из шаблона."""

import json
from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "config.template.json"


def generate_config(
    pair: str,
    api_port_inside_container: int,
    jwt_secret: str,
    ws_token: str,
    api_username: str,
    api_password: str,
    api_key_id: str | None,
    stake_amount: float,
    tradable_balance_ratio: float,
    dry_run: bool = True
) -> dict:
    """
    Возвращает готовый dict с конфигом для одного бота.

    api_port_inside_container — порт, который freqtrade слушает ВНУТРИ контейнера.
    Снаружи мы пробросим его на bot.api_port из БД через docker port mapping.
    Внутри пусть всегда будет 8080 (как в шаблоне) — это просто удобство.
    """
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    config["stake_amount"] = stake_amount
    config["tradable_balance_ratio"] = tradable_balance_ratio
    config["exchange"]["pair_whitelist"] = [pair]
    config["dry_run"] = dry_run

    config["api_server"]["listen_port"] = api_port_inside_container
    config["api_server"]["jwt_secret_key"] = jwt_secret
    config["api_server"]["ws_token"] = ws_token
    config["api_server"]["username"] = api_username
    config["api_server"]["password"] = api_password

    config["telegram"]["enabled"] = False

    return config


def write_config(config: dict, target_path: Path) -> None:
    """Сериализует и пишет config.json на диск."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
