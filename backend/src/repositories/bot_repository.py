from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select 
from src.models.bot import Bot
from src.models.user import User

class BotRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_all_active_bots(self):
        bots = await self.db.execute(select(Bot).where(Bot.status == "running", Bot.is_active == True))
        running_bots = bots.scalars().all()
        return running_bots
    
    async def get_user(self, bot_user_id): # это недоразумение нужно убрать
        user = await self.db.execute(select(User).where(User.id == bot_user_id))
        return user.scalar_one_or_none()
    
    async def get_bot_by_id(self, bot_id):
        result = await self.db.execute(select(Bot).where(Bot.id == bot_id))
        return result.scalar_one_or_none()
    
    async def get_all_busy_ports(self):
        result = await self.db.execute(select(Bot.api_port))
        return result.scalars().all()
    
    async def get_user_active_bots(self, user_id):
        result = await self.db.execute(select(Bot).where(Bot.user_id==user_id, Bot.is_active==True))
        bots = result.scalars().all()
        return bots
    
    async def get_user_bots(self, user_id):
        result = await self.db.execute(select(Bot).where(Bot.user_id==user_id))
        return result.scalars().all()
    