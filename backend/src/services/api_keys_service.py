from src.repositories.api_keys_repository import ApiKeysRepository
from src.schemas.api_keys import ApiKeyListItem
from src.core.crypto import encrypt
class ApiKeyService:
    def __init__(self,db):
        self.repo = ApiKeysRepository(db)

    async def get_list_api_keys(self, current_user):

        keys = await self.repo.user_active_keys(current_user.id)
        if keys is None: keys = []
        return [
            ApiKeyListItem(
                id=key.id,
                name=key.label,
                exchange=key.exchange,
                is_active=key.is_active,
                created_at= key.created_at
            )
            for key in keys
        ]
    
    async def create_api_key(self, current_user, payload):

        encrypted_key = encrypt(payload.api_key)
        encrypted_secret = encrypt(payload.api_secret)

        key = await self.repo.add_api_key(
            current_user.user_id,
            payload.exchange,
            payload.name,
            encrypted_key,
            encrypted_secret
        )

        return ApiKeyListItem(
            id=key.id,
            name=key.label,
            exchange=key.exchange,
            is_active=key.is_active,
            created_at=key.created_at,
        )

    async def delete_api_key(self, current_user, key_id):
        return await self.repo.delete_key(current_user.id, key_id)