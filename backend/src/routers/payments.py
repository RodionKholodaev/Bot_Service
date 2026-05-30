# routers/payments.py
import ipaddress
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.schemas.payments import PaymentCreate, PaymentCreateResponse
from yookassa import Configuration, Payment as YKPayment

from src.database import get_db
from src.models.user import User
from src.core.dependencies import get_current_user
from src.config import settings
from src.repositories.payments_repository import PaymentsRepository
from src.repositories.user_repository import UserRepository
from src.services import get_ip
router = APIRouter(prefix="/payments", tags=["payments"])

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


@router.post("/create", response_model=PaymentCreateResponse)
async def create_payment(
    body: PaymentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
    db_payment = await PaymentsRepository(db).create_payment(
        id=yk_payment.id,
        user_id=current_user.id,
        amount=body.amount,
        status="pending",  
    )

    return PaymentCreateResponse(
        payment_id=yk_payment.id, #type:ignore
        confirmation_url=yk_payment.confirmation.confirmation_url,#type:ignore
    )


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def payment_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    client_ip = get_ip(request) #type: ignore
    
    if not any(client_ip in network for network in YOOKASSA_IPS):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    body = await request.json()  # синхронный вариант не работает — см. примечание ниже
    event: str = body.get("event", "")
    obj: dict = body.get("object", {})

    if event != "payment.succeeded":
        return {"status": "ignored"}

    payment_id: str = obj["id"]
    amount: float = float(obj["amount"]["value"])
    user_id: int = int(obj["metadata"]["user_id"])

    db_payment = await PaymentsRepository(db).get_payment_by_id(payment_id)

    if db_payment is None:
        return {"status": "unknown_payment"}

    if db_payment.status == "succeeded":
        return {"status": "already_processed"}

    db_payment.status = "succeeded"

    user = await UserRepository(db).get_user_by_id(user_id)

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.service_balance += amount
    await db.commit()

    return {"status": "ok"}