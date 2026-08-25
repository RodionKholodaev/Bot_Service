from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.exchange_api_key import ExchangeApiKey


class ApiKeysRepository:
    def __init__(self, s: AsyncSession):
        self.db = s

    async def user_active_keys(self, user_id: int):
        result = await self.db.execute(select(ExchangeApiKey).where(ExchangeApiKey.user_id == user_id))
        if result is None:
            return None
        else:
            return result.scalars().all()

    async def add_api_key(self, user_id, exchange, label, key_enc, secret_enc):
        key = ExchangeApiKey(
            user_id=user_id,
            exchange=exchange,
            label=label,
            api_key_encrypted=key_enc,
            api_secret_encrypted=secret_enc,
            is_active=True,
        )
        self.db.add(key)
        await self.db.flush()
        await self.db.refresh(key)
        return key

    async def delete_key(self, user_id, api_key_id):
        result = await self.db.execute(
            select(ExchangeApiKey).where(ExchangeApiKey.user_id == user_id, ExchangeApiKey.id == api_key_id)
        )
        key = result.scalar_one_or_none()
        if key:
            await self.db.delete(key)
            await self.db.flush()

    async def get_api_key_by_id(self, key_id, user_id):
        """Ключ по id, но только среди ключей этого пользователя.

        user_id — обязательный аргумент, а не фильтр «по желанию вызывающего»:
        id ключа приходит из тела запроса на создание бота, и выборка по одному
        только id позволяла запустить контейнер на чужом биржевом ключе.
        """
        result = await self.db.execute(
            select(ExchangeApiKey).where(
                ExchangeApiKey.id == key_id,
                ExchangeApiKey.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
