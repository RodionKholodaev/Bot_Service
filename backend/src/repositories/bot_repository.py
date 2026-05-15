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
    
    async def get_user(self, bot_user_id):
        user = await self.db.execute(select(User).where(User.id == bot_user_id))
        return user.scalar_one_or_none()
    