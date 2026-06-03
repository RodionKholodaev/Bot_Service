from src.repositories.payments_repository import PaymentsRepository
import ipaddress
from fastapi import Request, status
from src.schemas.payments import PaymentCreate, PaymentCreateResponse
from yookassa import Configuration, Payment as YKPayment
from src.models.user import User
from src.config import settings
from src.repositories.user_repository import UserRepository
from src.services.get_ip import get_ip
from src.core.exceptions import NotFoundError, ForbiddenError

YOOKASSA_IPS = [
    ipaddress.ip_network("185.71.76.0/27"),
    ipaddress.ip_network("185.71.77.0/27"),
    ipaddress.ip_network("77.75.153.0/25"),
    ipaddress.ip_network("77.75.156.11/32"),
    ipaddress.ip_network("77.75.156.35/32"),
    ipaddress.ip_network("77.75.154.128/25"),
    ipaddress.ip_network("2a02:5180::/32"),
]


def _configure_yookassa():
    Configuration.account_id = settings.YOOKASSA_SHOP_ID
    Configuration.secret_key = settings.YOOKASSA_SECRET_KEY

class PaymentService:
    def __init__(self, db, user_repo, payment_repo):
        self.db = db
        self.payment_repo: PaymentsRepository = payment_repo
        self.user_repo: UserRepository = user_repo
    
    async def create_payment(self, request: Request, body: PaymentCreate, current_user: User):
        raw = await request.body()

        _configure_yookassa()

        yk_payment = YKPayment.create({
            "amount": {
                "value": f"{body.amount:.2f}",
                "currency": "RUB",
            },
            "confirmation": {
                "type": "redirect",
                "return_url": f"{settings.FRONTEND_URL}/?payment=success",
            },
            "capture": True,
            "description": f"Пополнение баланса CryptoBot, user_id={current_user.id}",
            "metadata": {
                "user_id": str(current_user.id),
            },
        })
        db_payment = await self.payment_repo.create_payment(
            id=yk_payment.id,
            user_id=current_user.id,
            amount=body.amount,
            status="pending",  
        )
        await self.db.commit()

        return PaymentCreateResponse(
            payment_id=yk_payment.id, #type:ignore
            confirmation_url=yk_payment.confirmation.confirmation_url,#type:ignore
        )
    
    async def process_payment_webhook(self, request: Request):

        client_ip = get_ip(request) #type: ignore
        
        if not any(client_ip in network for network in YOOKASSA_IPS):
            raise ForbiddenError()

        body = await request.json()
        event: str = body.get("event", "")
        obj: dict = body.get("object", {})

        if event != "payment.succeeded":
            return {"status": "ignored"}

        payment_id: str = obj["id"]
        amount: float = float(obj["amount"]["value"])
        user_id: int = int(obj["metadata"]["user_id"])

        db_payment = await self.payment_repo.get_payment_by_id(payment_id)

        if db_payment is None:
            return {"status": "unknown_payment"}

        if db_payment.status == "succeeded":
            return {"status": "already_processed"}

        db_payment.status = "succeeded"

        user = await self.user_repo.get_user_by_id(user_id)

        if user is None:
            raise NotFoundError("User not found")

        await self.user_repo.change_balanse(user, amount)
        await self.db.commit()

        return {"status": "ok"}