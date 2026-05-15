from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select 
from src.models.trade import Trade

class TradeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_trade(self, bot_id, ft_id):
        trade = await self.db.execute(select(Trade).where(Trade.bot_id == bot_id, Trade.freqtrade_trade_id==ft_id))
        return trade.scalar_one_or_none()
    
    async def get_all_close_trades(self, user_id):
        query = select(Trade).where(Trade.user_id == user_id, Trade.close_time.isnot(None))
        return query
    
    async def get_weekly_trades(self, user_id, since):
        result = await self.db.execute(select(Trade).filter(
            Trade.user_id == user_id,
            Trade.close_time.isnot(None),
            Trade.close_time >= since,
        ))
        return result.scalars().all()
    
    async def get_bot_close_trades(self, user_id, bot_id):
        query = select(Trade).where(Trade.user_id==user_id, Trade.bot_id==bot_id, Trade.close_time.isnot(None))
        return query
