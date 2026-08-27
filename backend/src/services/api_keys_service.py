import logging

from src.core.crypto import encrypt
from src.core.exceptions import NotFoundError
from src.repositories.api_keys_repository import ApiKeysRepository
from src.repositories.bot_repository import BotRepository
from src.schemas.api_keys import ApiKeyBalance, ApiKeyBalanceBot, ApiKeyListItem
from src.services import capital_guard
from src.services.exchange_account import (
    CcxtAccountClient,
    ExchangeAccountClient,
    ensure_supported_exchange,
    verify_key,
)

logger = logging.getLogger(__name__)


class ApiKeyService:
    def __init__(self, repo: ApiKeysRepository, exchange_client: ExchangeAccountClient | None = None):
        self.repo = repo
        # Клиент, если не передан, то CcxtAccountClient
        self.exchange_client: ExchangeAccountClient = exchange_client or CcxtAccountClient()

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
        """
        Сохраняет ключ, но только после того, как биржа подтвердила, что он рабочий.

        Раньше ключ принимался без единого обращения к бирже, и неверный, протухший
        или read-only ключ обнаруживался упавшим контейнером — постфактум, а причина
        была видна только в логах докера. Проверка стоит до encrypt(): негодный ключ
        не должен даже попасть в базу.
        """
        exchange = ensure_supported_exchange(payload.exchange)
        # Пробелы по краям — самая частая порча ключа при копировании из интерфейса
        # биржи; молча отдавать такой ключ в подпись значит получить «неверный ключ»
        # на ровном месте.
        api_key_value = payload.api_key.strip()
        api_secret_value = payload.api_secret.strip()

        await verify_key(self.exchange_client, exchange, api_key_value, api_secret_value)

        encrypted_key = encrypt(api_key_value)
        encrypted_secret = encrypt(api_secret_value)

        key = await self.repo.add_api_key(current_user.id, exchange, payload.name, encrypted_key, encrypted_secret)
        logger.info(
            "API key created",
            extra={
                "user_id": current_user.id,
                "key_id": key.id,
                "exchange": exchange,
            },
        )

        return ApiKeyListItem(
            id=key.id,
            name=key.label,
            exchange=key.exchange,
            is_active=key.is_active,
            created_at=key.created_at,
        )

    async def get_key_balance(self, current_user, key_id: int, bot_repo: BotRepository) -> ApiKeyBalance:
        """
        Сколько на ключе денег и сколько из них уже занято депозитами его ботов.
        Показывает лимит, пока человек вводит депозит, а не отказом на последнем шаге.
        """
        # получаем ключ
        api_key = await self.repo.get_api_key_by_id(key_id, current_user.id)
        # выбрасываем ошибку если его нет
        if api_key is None:
            # 404, а не 403: по коду ответа нельзя отличить чужой ключ от несуществующего
            raise NotFoundError("API-ключ не найден")
        # получаем ботов на этом ключе
        live_bots = await bot_repo.get_live_bots_on_key(api_key.id)
        # получаем сумарный капитал на ботов (в виде схемы)
        capital = await capital_guard.get_key_capital(self.exchange_client, api_key, list(live_bots))
        # возвращяем его
        return ApiKeyBalance(
            total=round(capital.total, 2),
            free=round(capital.free, 2),
            reserved=round(capital.reserved, 2),
            available=round(capital.available, 2),
            bots=[
                ApiKeyBalanceBot(id=item.id, name=item.name, stake_amount=round(item.stake_amount, 2))
                for item in capital.bots
            ],
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
