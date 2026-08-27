"""
Переиспользуемый фейк биржевого клиента (не тест, несмотря на префикс test_ —
так же, как соседние test_user_repository.py и test_consent_repository.py).

Заменяет CcxtAccountClient: запоминает, о чём его спрашивали, и отдаёт заранее
заданный ответ или заранее заданную ошибку. Настоящая сеть в юнит-тестах не нужна,
а ошибки биржи иначе не воспроизвести.
"""

from src.services.exchange_account import AccountBalance, KeyPermissions


class FakeExchangeAccountClient:
    """Fake вместо ExchangeAccountClient.

    balance/permissions — что вернуть; balance_error/permissions_error — что вместо
    этого поднять (уже переведённое доменное исключение, как его отдаёт настоящий
    клиент). calls хранит пары (метод, api_key) для проверки, ходили ли на биржу вообще.
    """

    def __init__(
        self,
        *,
        total: float = 1_000.0,
        free: float | None = None,
        permissions: KeyPermissions | None = None,
        balance_error: Exception | None = None,
        permissions_error: Exception | None = None,
    ):
        self.balance = AccountBalance(total=total, free=total if free is None else free)
        self.permissions = permissions or KeyPermissions(read_only=False, can_trade_futures=True, expires_at=None)
        self.balance_error = balance_error
        self.permissions_error = permissions_error
        self.calls: list[tuple[str, str]] = []

    async def fetch_balance(self, exchange: str, key: str, secret: str) -> AccountBalance:
        self.calls.append(("fetch_balance", key))
        if self.balance_error is not None:
            raise self.balance_error
        return self.balance

    async def fetch_permissions(self, exchange: str, key: str, secret: str) -> KeyPermissions:
        self.calls.append(("fetch_permissions", key))
        if self.permissions_error is not None:
            raise self.permissions_error
        return self.permissions
