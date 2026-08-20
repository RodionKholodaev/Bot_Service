import logging

from src.core.crypto import encrypt
from src.repositories.api_keys_repository import ApiKeysRepository
from src.schemas.api_keys import ApiKeyListItem

logger = logging.getLogger(__name__)


class ApiKeyService:
    def __init__(self, repo: ApiKeysRepository):
        self.repo = repo

    async def get_list_api_keys(self, current_user):

        keys = await self.repo.user_active_keys(current_user.id)
        if keys is None:
            keys = []
        return [
            ApiKeyListItem(
                id=key.id, name=key.label, exchange=key.exchange, is_active=key.is_active, created_at=key.created_at
            )
            for key in keys
        ]

    async def create_api_key(self, current_user, payload):

        encrypted_key = encrypt(payload.api_key)
        encrypted_secret = encrypt(payload.api_secret)

        key = await self.repo.add_api_key(
            current_user.id, payload.exchange, payload.name, encrypted_key, encrypted_secret
        )
        logger.info(
            "API key created",
            extra={
                "user_id": current_user.id,
                "key_id": key.id,
                "exchange": payload.exchange,
            },
        )

        return ApiKeyListItem(
            id=key.id,
            name=key.label,
            exchange=key.exchange,
            is_active=key.is_active,
            created_at=key.created_at,
        )

    async def delete_api_key(self, current_user, key_id):

        ans = await self.repo.delete_key(current_user.id, key_id)
        logger.info(
            "API key deleted",
            extra={
                "user_id": current_user.id,
                "key_id": key_id,
            },
        )
        return ans
