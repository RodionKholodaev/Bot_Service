"""Генерация config.json для каждого бота из шаблона."""

import json
from pathlib import Path
from src.core.crypto import decrypt
from sqlalchemy.ext.asyncio import AsyncSession
from src.repositories.api_keys_repository import ApiKeysRepository
TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "config.template.json"


async def generate_config(
    pair: str,
    api_port_inside_container: int,
    jwt_secret: str,
    ws_token: str,
    api_username: str,
    api_password: str,
    api_key_id: int | None,
    stake_amount: float,
    tradable_balance_ratio: float,
    db: AsyncSession,
    user_id: int,
    dry_run: bool = True,
) -> dict:
    """
    Возвращает готовый dict с конфигом для одного бота.

    api_port_inside_container — порт, который freqtrade слушает ВНУТРИ контейнера.
    Снаружи мы пробросим его на bot.api_port из БД через docker port mapping.
    Внутри пусть всегда будет 8080 (как в шаблоне) — это просто удобство.
    """
    if api_key_id is not None: 
        api_keys = await ApiKeysRepository(db).get_api_key_by_id(api_key_id)
        key = decrypt(api_keys.api_key_encrypted)
        secret = decrypt(api_keys.api_secret_encrypted)
    else:
        key = ""
        secret = ""
        
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    config["stake_amount"] = stake_amount
    config["tradable_balance_ratio"] = tradable_balance_ratio
    config["exchange"]["pair_whitelist"] = [pair]
    config["dry_run"] = dry_run
    config["exchange"]["key"] = key
    config["exchange"]["secret"] = secret
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
