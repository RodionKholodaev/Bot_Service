from sqlalchemy.ext.asyncio import AsyncSession

from src.models.consent_log import ConsentLog


class ConsentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        user_id: int,
        documents: list[tuple[str, str]],
        ip_address: str | None = None,
    ) -> None:
        """Записывает по строке на каждый принятый документ.

        documents — список пар (document_type, document_version) из
        src/core/legal.py. Только flush, без commit: согласия должны попасть в
        базу той же транзакцией, что и сам пользователь (её коммитит get_db в
        конце запроса) — иначе при сбое остался бы аккаунт без согласий.
        """
        self.db.add_all(
            [
                ConsentLog(
                    user_id=user_id,
                    document_type=document_type,
                    document_version=document_version,
                    ip_address=ip_address,
                )
                for document_type, document_version in documents
            ]
        )
        await self.db.flush()
