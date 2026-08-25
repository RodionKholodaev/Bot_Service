"""
Юнит-тесты вебхука ЮKassa — того, откуда берутся сумма и получатель пополнения.

Раньше и сумма, и user_id читались из тела запроса, а единственной защитой был
IP-фильтр по заголовку, который пишет сам клиент. То есть один HTTP-запрос
начислял произвольный баланс произвольному пользователю. Теперь тело даёт только
идентификатор платежа, всё остальное — своя БД и ответ самой ЮKassa.

Сети здесь нет: репозитории заменены фейками, а SDK ЮKassa — FakeYooKassaPayment.
"""

import pytest

from src.core.exceptions import ForbiddenError
from src.models.payment import Payment
from src.models.user import User
from src.services import payment_service as payment_service_module
from src.services.payment_service import PaymentService

# адрес из боевого whitelist — первый барьер тесты проходят честно
YOOKASSA_IP = "185.71.76.1"


class FakeRequest:
    """Fake вместо starlette Request — вебхуку нужны только заголовки и тело."""

    def __init__(self, payload: dict, *, forwarded_for: str = YOOKASSA_IP):
        self.headers = {"X-Forwarded-For": forwarded_for}
        self.client = None
        self._payload = payload

    async def json(self):
        return self._payload


class FakePaymentsRepo:
    """Fake вместо PaymentsRepository — один заранее созданный платёж."""

    def __init__(self, payment: Payment | None):
        self._payment = payment

    async def get_payment_by_id(self, payment_id):
        if self._payment is not None and self._payment.id == payment_id:
            return self._payment
        return None


class FakeUserRepo:
    """Fake вместо UserRepository — балансы в памяти."""

    def __init__(self, users: list[User]):
        self.users = {user.id: user for user in users}

    async def get_user_by_id(self, user_id):
        return self.users.get(user_id)

    async def change_balance(self, user, amount):
        user.service_balance += amount


class FakeAmount:
    def __init__(self, value: str):
        self.value = value


class FakeYooKassaPayment:
    """Fake вместо yookassa.Payment — подменяет обращение к API ЮKassa."""

    status = "succeeded"
    paid = True
    amount = FakeAmount("10.00")

    @classmethod
    def find_one(cls, payment_id):
        cls.requested_id = payment_id
        return cls


def make_payload(*, payment_id: str = "pay-1", amount: str = "10.00", user_id: str = "1") -> dict:
    """Тело вебхука. Сумма и user_id здесь — то, что подставил бы атакующий."""
    return {
        "event": "payment.succeeded",
        "object": {
            "id": payment_id,
            "amount": {"value": amount, "currency": "RUB"},
            "metadata": {"user_id": user_id},
        },
    }


def make_service(monkeypatch, *, payment: Payment | None, users: list[User]) -> tuple[PaymentService, FakeUserRepo]:
    monkeypatch.setattr(payment_service_module, "YKPayment", FakeYooKassaPayment)
    user_repo = FakeUserRepo(users)
    return PaymentService(user_repo, FakePaymentsRepo(payment)), user_repo


@pytest.mark.asyncio
async def test_amount_and_user_come_from_database_not_from_payload(monkeypatch):
    # Arrange
    payment = Payment(id="pay-1", user_id=1, amount=10.0, status="pending")
    payer = User(id=1, email="payer@test.com", service_balance=0.0)
    stranger = User(id=2, email="stranger@test.com", service_balance=0.0)
    service, user_repo = make_service(monkeypatch, payment=payment, users=[payer, stranger])

    # в теле — миллион на чужой аккаунт
    request = FakeRequest(make_payload(amount="1000000.00", user_id="2"))

    # Act
    result = await service.process_payment_webhook(request)  # type: ignore[arg-type]

    # Assert
    assert result == {"status": "ok"}
    # начислено ровно то, что подтвердила ЮKassa, и владельцу платежа из нашей БД
    assert payer.service_balance == 10.0
    assert stranger.service_balance == 0.0
    assert payment.status == "succeeded"
    assert user_repo.users[2].service_balance == 0.0


@pytest.mark.asyncio
async def test_webhook_rejected_when_yookassa_does_not_confirm(monkeypatch):
    # Arrange
    payment = Payment(id="pay-1", user_id=1, amount=10.0, status="pending")
    payer = User(id=1, email="payer@test.com", service_balance=0.0)
    service, _ = make_service(monkeypatch, payment=payment, users=[payer])
    # платёж на стороне ЮKassa не оплачен — вебхук подделан
    monkeypatch.setattr(FakeYooKassaPayment, "status", "pending")
    monkeypatch.setattr(FakeYooKassaPayment, "paid", False)

    # Act / Assert
    with pytest.raises(ForbiddenError):
        await service.process_payment_webhook(FakeRequest(make_payload()))  # type: ignore[arg-type]

    assert payer.service_balance == 0.0
    assert payment.status == "pending"


@pytest.mark.asyncio
async def test_spoofed_client_ip_is_rejected(monkeypatch):
    # Arrange
    payment = Payment(id="pay-1", user_id=1, amount=10.0, status="pending")
    payer = User(id=1, email="payer@test.com", service_balance=0.0)
    service, _ = make_service(monkeypatch, payment=payment, users=[payer])

    # так выглядит подделка при стандартном nginx: адрес ЮKassa прислал сам клиент,
    # реальный адрес прокси дописал в конец
    request = FakeRequest(make_payload(), forwarded_for=f"{YOOKASSA_IP}, 203.0.113.9")

    # Act / Assert
    with pytest.raises(ForbiddenError):
        await service.process_payment_webhook(request)  # type: ignore[arg-type]

    assert payer.service_balance == 0.0


@pytest.mark.asyncio
async def test_already_succeeded_payment_is_not_credited_twice(monkeypatch):
    # Arrange
    payment = Payment(id="pay-1", user_id=1, amount=10.0, status="succeeded")
    payer = User(id=1, email="payer@test.com", service_balance=10.0)
    service, _ = make_service(monkeypatch, payment=payment, users=[payer])

    # Act
    result = await service.process_payment_webhook(FakeRequest(make_payload()))  # type: ignore[arg-type]

    # Assert
    assert result == {"status": "already_processed"}
    assert payer.service_balance == 10.0
