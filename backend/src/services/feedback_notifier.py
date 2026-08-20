"""
Уведомляет разработчика в Telegram о новом отзыве.

Почему отдельно от core/telegram_alerts.py: тот канал подписан только на
logger.critical(), то есть на инциденты, и глушит повторы одного текста на
5 минут. Отзывы — это не инциденты, их поток нужно видеть целиком, поэтому
здесь свой бот и свой чат, который можно включить или выключить, не трогая
алерты.

Доставка — best effort: если Telegram недоступен, отзыв всё равно уже сохранён
в БД, и пользователь про проблему знать не должен. Поэтому функция ниже
не выбрасывает исключений наружу вообще.
"""

import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

# Телеграм отклоняет сообщения длиннее 4096 символов — оставляем запас
# (message в отзыве сам по себе может быть до 2000).
MAX_MESSAGE_LENGTH = 3500

SEND_TIMEOUT = 5.0

# Те же формулировки, что видит пользователь на странице /feedback.
TOPIC_LABELS = {
    "idea": "💡 Идея / предложение",
    "bug": "🐛 Баг",
    "ux": "🤔 Неудобно пользоваться",
    "other": "💬 Другое",
}


def feedback_notifications_enabled() -> bool:
    """Уведомления включены, только если в .env заданы и токен, и chat_id."""
    return bool(settings.TELEGRAM_FEEDBACK_BOT_TOKEN and settings.TELEGRAM_FEEDBACK_CHAT_ID)


def _build_message(feedback, user) -> str:
    lines = [
        f"Новый отзыв #{feedback.id}",
        TOPIC_LABELS.get(feedback.topic, feedback.topic),
    ]

    if feedback.rating is not None:
        lines.append(f"Оценка: {feedback.rating}/5")

    lines.append(f"От: user_id={user.id} ({user.email})")

    # почта, которую пользователь оставил именно для ответа — может отличаться
    # от почты аккаунта, а может отсутствовать вовсе
    if feedback.email:
        lines.append(f"Email для ответа: {feedback.email}")

    lines.append("")
    lines.append(feedback.message)

    return "\n".join(lines)[:MAX_MESSAGE_LENGTH]


async def notify_new_feedback(feedback, user) -> None:
    """Отправляет отзыв в Telegram. Никогда не бросает исключение наружу."""
    if not feedback_notifications_enabled():
        return

    try:
        url = TELEGRAM_API_URL.format(token=settings.TELEGRAM_FEEDBACK_BOT_TOKEN)
        # без parse_mode: текст отзыва пишет пользователь, и любая разметка
        # в нём иначе или сломает сообщение, или будет отвергнута Telegram
        payload = {
            "chat_id": settings.TELEGRAM_FEEDBACK_CHAT_ID,
            "text": _build_message(feedback, user),
        }

        async with httpx.AsyncClient(timeout=SEND_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

        logger.info(
            "Feedback notification sent to Telegram",
            extra={"feedback_id": feedback.id},
        )
    except Exception:
        # logger.exception, а не critical: отзыв уже в БД, ничего не потеряно,
        # будить разработчика посреди ночи из-за этого не нужно
        logger.exception(
            "Failed to deliver feedback notification to Telegram",
            extra={"feedback_id": getattr(feedback, "id", None)},
        )
