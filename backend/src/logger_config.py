import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"

# Набор стандартных полей LogRecord — всё, чего нет в этом наборе, пришло через extra={...}.
STANDARD_LOG_RECORD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


def extra_fields(record: logging.LogRecord) -> dict:
    """Достаёт только те поля LogRecord, что пришли через extra={...} (используется
    и форматтером логов ниже, и telegram_alerts.py — чтобы не дублировать логику)."""
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in STANDARD_LOG_RECORD_ATTRS
    }


class ExtraFormatter(logging.Formatter):
    """Дописывает поля из extra={...} в конец строки — иначе logging.basicConfig их молча отбрасывает."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extra_items = extra_fields(record)
        if extra_items:
            extra_str = " ".join(f"{key}={value!r}" for key, value in extra_items.items())
            return f"{base} | {extra_str}"
        return base


def setup_logging():
    formatter = ExtraFormatter(
        fmt='%(levelname)s:     %(asctime)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        LOG_DIR / "app.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler])


"""
формат вывода:
INFO:     2026-05-31 12:34:56 - [main.py:25] - Сервер запущен
ERROR:    2026-05-31 12:34:57 - [bots.py:42] - Ошибка подключения к БД
INFO:     2026-05-31 12:35:01 - [bot_service.py:80] - Bot created | user_id=3 bot_id='a1b2c3'
"""
