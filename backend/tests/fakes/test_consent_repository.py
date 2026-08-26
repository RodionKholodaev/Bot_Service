"""Фейк ConsentRepository — это не тестовый модуль, несмотря на префикс test_.

Настоящий репозиторий пишет строки в consent_log через AsyncSession; здесь
вместо базы обычный список, по которому тест проверяет, какие именно согласия
и с какой версией были записаны.
"""


class FakeConsentRepository:
    """Заменяет src.repositories.consent_repository.ConsentRepository."""

    def __init__(self):
        self.rows: list[dict] = []

    async def log(self, user_id: int, documents: list[tuple[str, str]], ip_address: str | None = None) -> None:
        for document_type, document_version in documents:
            self.rows.append(
                {
                    "user_id": user_id,
                    "document_type": document_type,
                    "document_version": document_version,
                    "ip_address": ip_address,
                }
            )

    def types(self) -> list[str]:
        """Коды записанных документов в порядке записи."""
        return [row["document_type"] for row in self.rows]
