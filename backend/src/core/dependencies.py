from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import decode_token
from src.database import get_db
from src.models.user import User
from src.repositories.api_keys_repository import ApiKeysRepository
from src.repositories.assistant_request_repository import AssistantRequestRepository
from src.repositories.bot_repository import BotRepository
from src.repositories.consent_repository import ConsentRepository
from src.repositories.feedback_repository import FeedbackRepository
from src.repositories.payments_repository import PaymentsRepository
from src.repositories.trade_repository import TradeRepository
from src.repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer()


async def get_bot_repo(db: AsyncSession = Depends(get_db)):
    return BotRepository(db)


async def get_payments_repo(db: AsyncSession = Depends(get_db)):
    return PaymentsRepository(db)


async def get_trade_repo(db: AsyncSession = Depends(get_db)):
    return TradeRepository(db)


async def get_user_repo(db: AsyncSession = Depends(get_db)):
    return UserRepository(db)


async def get_consent_repo(db: AsyncSession = Depends(get_db)):
    return ConsentRepository(db)


async def get_api_key_repo(db: AsyncSession = Depends(get_db)):
    return ApiKeysRepository(db)


async def get_feedback_repo(db: AsyncSession = Depends(get_db)):
    return FeedbackRepository(db)


async def get_assistant_request_repo(db: AsyncSession = Depends(get_db)):
    return AssistantRequestRepository(db)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    user_id = decode_token(token)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный или отсутствующий токен",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден",
        )

    # Без этой проверки поле User.is_active было чисто декоративным: у заблокированного
    # пользователя оставался рабочий токен, а значит и боты, и оплата, и всё остальное.
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован",
        )

    return user
