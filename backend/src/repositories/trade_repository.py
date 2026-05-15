from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select 
from src.models.trade import Trade

class TradeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_trade(self, bot_id, ft_id):
        trade = await self.db.execute(select(Trade).where(Trade.bot_id == bot_id, Trade.freqtrade_trade_id==ft_id))
        return trade.scalar_one_or_none()
    
