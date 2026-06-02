from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select 
from src.models.payment import Payment
from src.models.user import User
class PaymentsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_payment(self,id, user_id, amount, status):
        payment = Payment(
            id = id,
            user_id=user_id,
            amount= amount,
            status = status
        )
        self.db.add(payment)
        await self.db.flush()
        return payment
    
    async def get_payment_by_id(self,payment_id):
        result = await self.db.execute(select(Payment).where(Payment.id ==payment_id))
        return result.scalar_one_or_none()
    


