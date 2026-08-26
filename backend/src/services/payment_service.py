import asyncio
import ipaddress
import logging

from fastapi import Request
from yookassa import Configuration
from yookassa import Payment as YKPayment

from src.config import settings
from src.core.exceptions import ForbiddenError, NotFoundError
from src.models.user import User
from src.repositories.payments_repository import PaymentsRepository
from src.repositories.user_repository import UserRepository
from src.schemas.payments import PaymentCreate, PaymentCreateResponse
from src.services.get_ip import get_ip

logger = logging.getLogger(__name__)

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
    logger.debug("YooKassa SDK configured")


class PaymentService:
    def __init__(self, user_repo, payment_repo):
        self.payment_repo: PaymentsRepository = payment_repo
        self.user_repo: UserRepository = user_repo
        logger.debug("PaymentService initialized")

    async def create_payment(self, request: Request, body: PaymentCreate, current_user: User):
        logger.info(
            "Creating payment",
            extra={"user_id": current_user.id, "amount": body.amount},
        )

        _configure_yookassa()

        yk_payment = YKPayment.create(
            {
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
            }
        )
        logger.info(
            "YooKassa payment created",
            extra={
                "payment_id": yk_payment.id,
                "user_id": current_user.id,
                "amount": body.amount,
            },
        )

        await self.payment_repo.create_payment(
            id=yk_payment.id,
            user_id=current_user.id,
            amount=body.amount,
            status="pending",
        )
        logger.info(
            "Payment record saved to database",
            extra={"payment_id": yk_payment.id, "status": "pending"},
        )

        return PaymentCreateResponse(
            payment_id=yk_payment.id,  # type: ignore
            confirmation_url=yk_payment.confirmation.confirmation_url,  # type: ignore
        )

    async def process_payment_webhook(self, request: Request):
        client_ip = get_ip(request)

        logger.info(
            "Processing payment webhook",
            extra={"client_ip": str(client_ip)},
        )

        # Первый барьер. Не единственный: подписи у вебхуков ЮKassa нет, а сам
        # заголовок с адресом приходит от клиента, поэтому ниже статус платежа
        # ещё и перепроверяется прямым запросом в ЮKassa.
        if client_ip is None or not any(client_ip in network for network in YOOKASSA_IPS):
            logger.warning(
                "Webhook rejected: IP not in YooKassa whitelist",
                extra={"client_ip": str(client_ip)},
            )
            raise ForbiddenError()

        body = await request.json()
        event: str = body.get("event", "")
        obj: dict = body.get("object", {}) or {}

        logger.debug(
            "Webhook payload received",
            extra={"event": event, "payment_id": obj.get("id")},
        )

        if event != "payment.succeeded":
            logger.info(
                "Webhook event ignored",
                extra={"event": event, "payment_id": obj.get("id")},
            )
            return {"status": "ignored"}

        # Из тела берём ТОЛЬКО идентификатор платежа. Сумма и получатель раньше
        # тоже читались отсюда — то есть любой, кто дотянулся до этой ручки,
        # начислял себе произвольный баланс. Теперь это данные из нашей БД и из
        # ответа самой ЮKassa.
        payment_id = obj.get("id")
        if not isinstance(payment_id, str) or not payment_id:
            logger.warning("Webhook rejected: no payment id in payload")
            raise ForbiddenError()

        db_payment = await self.payment_repo.get_payment_by_id(payment_id)

        if db_payment is None:
            logger.warning(
                "Payment not found in database",
                extra={"payment_id": payment_id},
            )
            return {"status": "unknown_payment"}

        if db_payment.status == "succeeded":
            logger.info(
                "Payment already processed",
                extra={"payment_id": payment_id},
            )
            return {"status": "already_processed"}

        amount = await self._confirm_payment(payment_id, db_payment)

        user_id: int = db_payment.user_id

        logger.info(
            "Processing successful payment",
            extra={"payment_id": payment_id, "amount": amount, "user_id": user_id},
        )

        db_payment.status = "succeeded"

        user = await self.user_repo.get_user_by_id(user_id)

        if user is None:
            logger.error(
                "User not found for payment",
                extra={"payment_id": payment_id, "user_id": user_id},
            )
            raise NotFoundError("User not found")

        await self.user_repo.change_balance(user, amount)
        logger.info(
            "User balance updated after successful payment",
            extra={
                "payment_id": payment_id,
                "user_id": user_id,
                "amount": amount,
                "new_balance": user.service_balance,
            },
        )

        return {"status": "ok"}

    @staticmethod
    async def _confirm_payment(payment_id: str, db_payment) -> float:
        """Спрашивает ЮKassa, оплачен ли платёж, и возвращает оплаченную сумму.

        Это и есть настоящая проверка подлинности вебхука: подписи у ЮKassa нет,
        а IP-фильтр держится на правильной настройке прокси. Ответ на GET
        /payments/{id} подделать нельзя — он идёт по HTTPS с нашим shop_id.

        Ошибка сети/API не глушится: без подтверждения баланс не пополняем, а
        ЮKassa повторит вебхук (до нескольких раз в течение суток).
        """
        _configure_yookassa()

        # SDK синхронный, а мы в единственном event loop — иначе на время запроса
        # встали бы все остальные запросы приложения.
        yk_payment = await asyncio.to_thread(YKPayment.find_one, payment_id)

        status = getattr(yk_payment, "status", None)
        paid = getattr(yk_payment, "paid", False)

        if status != "succeeded" or not paid:
            logger.warning(
                "Webhook rejected: YooKassa does not confirm the payment",
                extra={"payment_id": payment_id, "yookassa_status": status, "paid": paid},
            )
            raise ForbiddenError()

        amount = float(yk_payment.amount.value)  # type: ignore

        # Расхождение с суммой, на которую платёж создавался, — аномалия: либо
        # частичная оплата, либо кто-то трогал платёж мимо нас. Начисляем то, что
        # реально оплачено, но об этом нужно узнать.
        if abs(amount - db_payment.amount) > 0.01:
            logger.critical(
                "Paid amount differs from the created payment",
                extra={
                    "payment_id": payment_id,
                    "expected_amount": db_payment.amount,
                    "paid_amount": amount,
                },
            )

        return amount
