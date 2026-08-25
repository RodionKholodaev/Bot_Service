"""
Тест ApiKeysRepository против настоящей (тестовой) БД.

Юнит-тесты BotService работают с фейковым репозиторием, поэтому сам SQL-фильтр
«ключ принадлежит этому пользователю» ими не проверяется — убери его, и они
останутся зелёными. Здесь выполняется реальный запрос: без этого теста
возвращённая по одному id чужая запись ExchangeApiKey никем не ловится.
"""

import pytest

from src.core.crypto import encrypt
from src.models.exchange_api_key import ExchangeApiKey
from src.models.user import User
from src.repositories.api_keys_repository import ApiKeysRepository


async def make_user(db_session, *, email: str) -> User:
    """Пользователь в БД — ключу нужен реальный владелец."""
    user = User(username="rodion", email=email, password_hash="hash")
    db_session.add(user)
    await db_session.flush()
    return user


async def make_api_key(db_session, *, owner: User) -> ExchangeApiKey:
    """Ключ биржи, зашифрованный так же, как его кладёт ApiKeyService."""
    key = ExchangeApiKey(
        user_id=owner.id,
        exchange="bybit",
        label="Мой Bybit",
        api_key_encrypted=encrypt("key"),
        api_secret_encrypted=encrypt("secret"),
        is_active=True,
    )
    db_session.add(key)
    await db_session.flush()
    return key


@pytest.mark.asyncio
async def test_api_key_is_returned_to_its_owner(db_session):
    owner = await make_user(db_session, email="owner@test.com")
    key = await make_api_key(db_session, owner=owner)

    found = await ApiKeysRepository(db_session).get_api_key_by_id(key.id, owner.id)

    assert found is not None
    assert found.id == key.id


@pytest.mark.asyncio
async def test_api_key_of_another_user_is_not_returned(db_session):
    owner = await make_user(db_session, email="owner@test.com")
    stranger = await make_user(db_session, email="stranger@test.com")
    key = await make_api_key(db_session, owner=owner)

    # тот же id ключа, но спрашивает не владелец — именно так выглядела попытка
    # запустить бота на чужом биржевом ключе
    found = await ApiKeysRepository(db_session).get_api_key_by_id(key.id, stranger.id)

    assert found is None
