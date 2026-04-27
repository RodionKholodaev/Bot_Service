from dataclasses import dataclass

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from src.models.exchange_api_key import ExchangeApiKey
from src.core.crypto import decrypt  


@dataclass
class ApiKeyData:
    """Расшифрованные данные ключа, готовые к передаче в freqtrade-конфиг."""
    id: int
    exchange: str
    label: str
    api_key: str
    api_secret: str


def get_api_key_by_id(key_id: int, user_id: int, db: Session) -> ApiKeyData:
    """
    Получить API-ключ по id синхронно.
    Проверяет принадлежность ключа пользователю.
    Расшифровывает api_key и api_secret перед возвратом.

    Используется при запуске бота — вызывается из bot-сервиса.

    Raises:
        HTTPException 404 — ключ не найден или не принадлежит пользователю.
        HTTPException 403 — ключ деактивирован.
    """
    key = (
        db.query(ExchangeApiKey)
        .filter(
            ExchangeApiKey.id == key_id,
            ExchangeApiKey.user_id == user_id,
        )
        .first()
    )

    if key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API-ключ {key_id} не найден",
        )

    if not key.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API-ключ '{key.label}' деактивирован",
        )

    return ApiKeyData(
        id=key.id,
        exchange=key.exchange,
        label=key.label,
        api_key=decrypt(key.api_key_encrypted),
        api_secret=decrypt(key.api_secret_encrypted),
    )