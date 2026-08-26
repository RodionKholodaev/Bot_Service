import logging

from src.core.exceptions import BadRequestError, ConflictError, UnauthorizedError
from src.core.legal import (
    CROSS_BORDER_TRANSFER,
    DOC_CROSS_BORDER,
    DOC_MARKETING,
    DOC_PDN_CONSENT,
    DOC_TERMS,
    MARKETING_CONSENT_VERSION,
    PDN_CONSENT_VERSION,
    TERMS_VERSION,
)
from src.core.security import create_token, hash_password, verify_password
from src.models.user import User
from src.repositories.consent_repository import ConsentRepository
from src.repositories.user_repository import UserRepository
from src.schemas.user import TokenResponse

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, repo: UserRepository, consent_repo: ConsentRepository):
        self.repo = repo
        self.consent_repo = consent_repo

    @staticmethod
    def _collect_consents(body) -> list[tuple[str, str]]:
        """Проверяет обязательные согласия и собирает список строк для consent_log.

        Проверка живёт здесь, а не только в браузере, намеренно: чекбоксы
        обходятся одним запросом мимо формы, а согласие должно быть доказуемым.
        Возвращает пары (document_type, document_version) — версии берём из
        src/core/legal.py, а не из тела запроса.
        """
        missing = []
        if not body.accept_terms:
            missing.append("Пользовательское соглашение")
        if not body.accept_pdn:
            missing.append("Согласие на обработку персональных данных")
        if CROSS_BORDER_TRANSFER and not body.accept_cross_border:
            missing.append("Согласие на трансграничную передачу персональных данных")

        if missing:
            raise BadRequestError("Для регистрации необходимо принять: " + ", ".join(missing))

        consents = [
            (DOC_TERMS, TERMS_VERSION),
            (DOC_PDN_CONSENT, PDN_CONSENT_VERSION),
        ]
        if CROSS_BORDER_TRANSFER:
            # Галочка отдельная, но это пункт того же документа — поэтому и
            # версия у неё от Согласия на обработку ПДн.
            consents.append((DOC_CROSS_BORDER, PDN_CONSENT_VERSION))
        if body.accept_marketing:
            consents.append((DOC_MARKETING, MARKETING_CONSENT_VERSION))

        return consents

    async def register(self, body, client_ip: str | None = None):
        # Сначала галочки: это чистая проверка тела запроса, без похода в базу.
        consents = self._collect_consents(body)

        if await self.repo.email_exists(body.email):
            logger.warning("Registration failed: email already exists", extra={"email": body.email})
            raise ConflictError("Email уже занят")

        user = User(
            username=body.username,
            email=body.email,
            password_hash=hash_password(body.password),
        )
        await self.repo.create_user(user)

        # Тот же flush, что и пользователь, и тот же коммит в конце запроса:
        # аккаунта без записанных согласий в базе появиться не должно.
        await self.consent_repo.log(user.id, consents, ip_address=client_ip)

        logger.info(
            "User registered",
            extra={
                "user_id": user.id,
                "email": user.email,
                "consents": [document_type for document_type, _ in consents],
            },
        )

        return TokenResponse(
            access_token=create_token(user.id),
            user_id=user.id,
            username=user.username,
        )

    async def login(self, body):
        user = await self.repo.get_user(body.email)
        if not user or not verify_password(body.password, user.password_hash):
            logger.warning(
                "Login failed",
                extra={
                    "email": body.email,
                },
            )

            raise UnauthorizedError("Неверный email или пароль")

        logger.info(
            "User logged in",
            extra={
                "user_id": user.id,
            },
        )

        return TokenResponse(
            access_token=create_token(user.id),
            user_id=user.id,
            username=user.username,
        )
