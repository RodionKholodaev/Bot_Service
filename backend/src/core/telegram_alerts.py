"""
Отправляет критичные (logger.critical(...)) логи в Telegram разработчику.

Важно: хендлер подписан только на уровень CRITICAL, а не на все ERROR/EXCEPTION
подряд. В проекте logger.error()/.exception() уже используется в десятках мест
на ожидаемые, самовосстанавливающиеся сбои — например, один freqtrade-контейнер
не ответил за 5 секунд. Если слать алерт на каждый такой случай, уведомления
быстро превратятся в шум, который проще выключить, чем читать.

CRITICAL — осознанный, короткий список мест в коде, которые сейчас реально
нужно увидеть сразу, а не при следующей проверке логов (например: воркер
синхронизации сделок упал целиком, курс USDT/RUB не удалось получить после
всех попыток). Чтобы добавить новую точку алерта, этот файл трогать не нужно —
просто в нужном месте кода использовать logger.critical("...", extra={...}).
"""

import logging
import sys
import threading
import time
import traceback

import httpx

from src.logger_config import extra_fields

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

# Не слать повторно один и тот же текст алерта чаще, чем раз в этот промежуток —
# защита от спама, если критичная ошибка зациклится (например, воркер падает
# и перезапускается каждые 30 секунд подряд несколько часов).
DEDUP_WINDOW_SECONDS = 300

# Телеграм отклоняет сообщения длиннее 4096 символов — оставляем запас.
MAX_MESSAGE_LENGTH = 3500


class TelegramAlertHandler(logging.Handler):
    """logging.Handler, отправляющий запись лога в Telegram-чат разработчика.

    Сама отправка идёт в отдельном потоке: приложение асинхронное (FastAPI +
    asyncio-воркер), и блокирующий HTTP-запрос к Telegram внутри emit() иначе
    тормозил бы event loop на время сетевого запроса.
    """

    def __init__(self, bot_token: str, chat_id: str):
        super().__init__(level=logging.CRITICAL)
        self._bot_token = bot_token
        self._chat_id = chat_id
        # Текст алерта -> время последней отправки (time.monotonic()).
        # Не подчищается со временем — при том небольшом числе разных critical-сообщений,
        # что реально есть в проекте, это не проблема.
        self._last_sent_at: dict[str, float] = {}
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            text = self._build_message(record)
        except Exception:
            # Ошибка при сборке текста алерта не должна ронять логирование в приложении.
            self.handleError(record)
            return

        if self._is_duplicate(text):
            return

        threading.Thread(target=self._send, args=(text,), daemon=True).start()

    def _build_message(self, record: logging.LogRecord) -> str:
        lines = [
            f"[CRITICAL] Bot_Service — {record.name}",
            record.getMessage(),
        ]

        fields = extra_fields(record)
        if fields:
            lines.append(" ".join(f"{key}={value!r}" for key, value in fields.items()))

        if record.exc_info:
            # Полный traceback остаётся в backend/logs/app.log — сюда достаточно
            # короткой строки "ТипИсключения: текст", чтобы уведомление можно
            # было прочитать одним взглядом с телефона.
            exc_line = "".join(traceback.format_exception_only(*record.exc_info[:2])).strip()
            lines.append(exc_line)

        return "\n".join(lines)[:MAX_MESSAGE_LENGTH]

    def _is_duplicate(self, text: str) -> bool:
        now = time.monotonic()
        with self._lock:
            last_sent = self._last_sent_at.get(text)
            if last_sent is not None and now - last_sent < DEDUP_WINDOW_SECONDS:
                return True
            self._last_sent_at[text] = now
        return False

    def _send(self, text: str) -> None:
        url = TELEGRAM_API_URL.format(token=self._bot_token)
        try:
            httpx.post(url, json={"chat_id": self._chat_id, "text": text}, timeout=5.0)
        except Exception as exc:
            # Нельзя логировать эту ошибку через logger.critical/.error — если проблема
            # именно в недоступности Telegram, это создаст бесконечный цикл алертов о себе же.
            print(f"[telegram_alerts] failed to deliver alert: {exc}", file=sys.stderr)


def setup_telegram_alerts(bot_token: str | None, chat_id: str | None) -> None:
    """Подключает TelegramAlertHandler к root-логгеру, если заданы токен и chat_id.

    Без них (например, в дев-окружении) — приложение просто работает без
    Telegram-алертов, ничего не падает.
    """
    logger = logging.getLogger(__name__)

    if not bot_token or not chat_id:
        logger.warning(
            "Telegram alerts disabled: TELEGRAM_ALERT_BOT_TOKEN or TELEGRAM_ALERT_CHAT_ID is not set"
        )
        return

    logging.getLogger().addHandler(TelegramAlertHandler(bot_token, chat_id))
    logger.info("Telegram alerts enabled")
