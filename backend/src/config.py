from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── База / JWT ────────────────────────────────────────
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    FERNET_KEY: str
    
    # ── Запуск ботов ──────────────────────────────────────
    # Папка, где будут лежать данные каждого бота (config.json, стратегия, логи, sqlite).
    # Дефолт — ./bots_data/ в корне проекта (рядом с cryptobot.db).
    BOTS_DATA_DIR: Path = BASE_DIR / "bots_data"

    # Имя Docker-образа freqtrade. Можно переопределить в .env.
    FREQTRADE_IMAGE: str = "freqtradeorg/freqtrade:stable"

    # Имя Docker-сети, в которой крутятся все боты.
    DOCKER_NETWORK_NAME: str = "cryptobot-network"

    # Диапазон портов для REST API ботов. Каждый бот получает свой порт из этого диапазона.
    BOT_API_PORT_RANGE_START: int = 9000
    BOT_API_PORT_RANGE_END: int = 9999

    # Хост, по которому бэкенд (запущенный с хоста) ходит в API ботов.
    # Поскольку контейнеры пробрасывают порт на хост — это localhost.
    BOT_API_HOST: str = "127.0.0.1"


settings = Settings()  # type: ignore
