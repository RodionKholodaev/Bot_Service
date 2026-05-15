from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select 
from src.models.user import User

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def email_exists(self, email):
        result = await self.db.execute(select(User).where(User.email==email))
        return result.scalar_one_or_none() is not None
    
    async def get_user(self, email):
        user = await self.db.execute(select(User).where(User.email ==email))
        return user.scalar_one_or_none()
    
    async def get_user_by_id(self, user_id):
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        return user

    