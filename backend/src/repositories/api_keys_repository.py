from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select 
from src.core.crypto import encrypt
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
        
    async def add_api_key(self, user_id, payload):
        key = ExchangeApiKey(
            user_id=user_id,
            exchange=payload.exchange,
            label=payload.name,
            api_key_encrypted=encrypt(payload.api_key),
            api_secret_encrypted=encrypt(payload.api_secret),
            is_active=True,
        )
        self.db.add(key)
        await self.db.commit()
        await self.db.refresh(key)
        return key

    async def delete_key(self, user_id, api_key_id):
        result = await self.db.execute(select(ExchangeApiKey).where(
            ExchangeApiKey.user_id == user_id, 
            ExchangeApiKey.id == api_key_id
            ))
        key = result.scalar_one_or_none()
        if key:
            await self.db.delete(key)
            await self.db.commit()
        
    async def get_api_key_by_id(self, key_id):
        result = await self.db.execute(select(ExchangeApiKey).where(ExchangeApiKey.id == key_id))
        return result.scalar_one_or_none()
    