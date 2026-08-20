from pydantic import BaseModel, Field


class PaymentCreate(BaseModel):
    amount: float = Field(..., ge=10, description="Сумма пополнения в рублях, минимум 10")


class PaymentCreateResponse(BaseModel):
    payment_id: str
    confirmation_url: str
