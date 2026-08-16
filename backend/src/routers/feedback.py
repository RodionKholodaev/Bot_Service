"""HTTP-слой обратной связи: приём отзывов со страницы /feedback."""

from fastapi import APIRouter, Depends, status

from src.core.dependencies import get_current_user, get_feedback_repo
from src.models.user import User
from src.repositories.feedback_repository import FeedbackRepository
from src.schemas.feedback import FeedbackCreate, FeedbackOut
from src.services.feedback_service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    payload: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    repo: FeedbackRepository = Depends(get_feedback_repo),
):
    """Сохранить отзыв залогиненного пользователя."""
    return await FeedbackService(repo).create_feedback(current_user, payload)
