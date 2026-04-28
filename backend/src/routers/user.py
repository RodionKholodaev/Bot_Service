from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.models.user import User
from src.core.dependencies import get_current_user

router = APIRouter(prefix="/users", tags=["users"])


class BalanceResponse(BaseModel):
    service_balance: float


@router.get("/me/balance", response_model=BalanceResponse)
def get_my_balance(current_user: User = Depends(get_current_user)) -> BalanceResponse:
    """Возвращает текущий баланс сервиса (для оплаты комиссии) у залогиненного пользователя."""
    return BalanceResponse(service_balance=current_user.service_balance)


