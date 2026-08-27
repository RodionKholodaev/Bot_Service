from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApiKeyListItem(BaseModel):
    """Отдаётся фронту — без секретов."""

    id: int
    name: str  # label в БД
    exchange: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApiKeyCreate(BaseModel):
    name: str
    exchange: str
    api_key: str
    api_secret: str


class ApiKeyBalanceBot(BaseModel):
    """Один бот, чей депозит уже занимает капитал ключа."""

    id: str
    name: str
    stake_amount: float


class ApiKeyBalance(BaseModel):
    """Раскладка капитала ключа в USDT — её же интерфейс показывает при вводе депозита.

    available = total - reserved и может быть отрицательным: боты могли быть созданы
    до появления этой проверки или деньги вывели со счёта уже после.
    """

    total: float
    free: float
    reserved: float
    available: float
    bots: list[ApiKeyBalanceBot] = []
