# routers/payments.py
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from src.schemas.payments import PaymentCreate, PaymentCreateResponse
from src.database import get_db
from src.models.user import User
from src.core.dependencies import get_current_user
from src. services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/create", response_model=PaymentCreateResponse)
async def create_payment(
    request: Request,
    body: PaymentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await PaymentService(db).create_payment(request,body, current_user)


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def payment_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    return await PaymentService(db).process_payment_webhook(request)
