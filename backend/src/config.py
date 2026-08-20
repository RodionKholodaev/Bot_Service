from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

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
    GLITCHTIP_DSN: str
    SERVICE_COMMISION: float

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

    YOOKASSA_SHOP_ID: str
    YOOKASSA_SECRET_KEY: str
    FRONTEND_URL: str

    # ── Telegram-алерты для разработчика ───────────────────
    # Токен бота (от @BotFather) и chat_id, куда слать critical-логи.
    # Не заданы — алерты просто выключены, приложение работает как раньше.
    TELEGRAM_ALERT_BOT_TOKEN: str | None = None
    TELEGRAM_ALERT_CHAT_ID: str | None = None
    SENTRY_ENVIRONMENT: str = "development"

    # ── Telegram-уведомления о новых отзывах ───────────────
    # Отдельный канал от алертов выше: там инциденты (critical-логи), тут поток
    # отзывов со страницы /feedback. Бот можно взять тот же, чат — любой.
    # Не заданы — уведомления выключены, отзыв просто сохраняется в БД.
    TELEGRAM_FEEDBACK_BOT_TOKEN: str | None = None
    TELEGRAM_FEEDBACK_CHAT_ID: str | None = None

    # ── ИИ-ассистент на странице создания бота (AITunnel) ──
    # Ключ вида sk-aitunnel-... . Не задан — ассистент просто выключен,
    # эндпоинт /assistant/chat отвечает 400 и фронт прячет панель.
    AITUNNEL_API_KEY: str | None = None
    AITUNNEL_BASE_URL: str = "https://api.aitunnel.ru/v1"

    # Модель для диалога. Обязана уметь tool calling. Список: https://aitunnel.ru/models
    AI_ASSISTANT_MODEL: str = "gpt-4.1-mini"

    # Модель для веб-поиска: perplexity sonar сама ходит в интернет и возвращает ссылки.
    AI_SEARCH_MODEL: str = "sonar"

    # Таймаут одного запроса к AITunnel, секунды.
    AI_ASSISTANT_TIMEOUT: float = 120.0


settings = Settings()  # type: ignore
