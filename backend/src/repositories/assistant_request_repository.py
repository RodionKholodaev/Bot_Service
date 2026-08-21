from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.assistant_request_log import AssistantRequestLog


class AssistantRequestRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def count_since(self, user_id: int, since: datetime) -> int:
        """Сколько запросов к ассистенту пользователь сделал начиная с момента since."""
        result = await self.db.execute(
            select(func.count())
            .select_from(AssistantRequestLog)
            .where(AssistantRequestLog.user_id == user_id, AssistantRequestLog.created_at >= since)
        )
        return result.scalar_one()

    async def create(self, user_id: int) -> AssistantRequestLog:
        """Отмечает запрос и сразу коммитит.

        Здесь намеренный отход от общей схемы «коммитит get_db в конце запроса»:
        ответ ассистента — это StreamingResponse, и коммит по общей схеме
        случился бы только после закрытия стрима (до AI_ASSISTANT_TIMEOUT секунд).
        Это дало бы сразу две проблемы: открытая write-транзакция на всё это время
        блокирует запись остальным (SQLite пускает одного писателя), а обрыв стрима
        откатил бы строку — и лимит обходился бы простым «нажать Стоп».
        """
        entry = AssistantRequestLog(user_id=user_id)
        self.db.add(entry)
        await self.db.commit()
        return entry
