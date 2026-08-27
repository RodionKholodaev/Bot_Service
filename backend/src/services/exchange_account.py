"""
Единственное место, где бэкенд сам ходит на биржу.

До этого модуля бэкенд принципиально не знал биржевого API: он говорил только с
freqtrade-API каждого бота, а ключ уходил в config.json контейнера непроверенным.
Плата за это — неверный, протухший или read-only ключ обнаруживался упавшим
контейнером, постфактум, и причина была видна только в логах докера.

Здесь ровно два действия, оба read-only и оба на редких путях (добавление ключа,
создание/запуск бота):
  * fetch_balance     — сколько денег на ключе; на нём же стоит проверка капитала
                        (services/capital_guard.py);
  * fetch_permissions — что этому ключу вообще позволено; fetch_balance доказывает
                        только право на чтение, а бот должен ещё и торговать.

Почему синхронный ccxt в asyncio.to_thread, а не ccxt.async_support: async-версия
требует обязательного `await exchange.close()` на каждом выходе, иначе в единственном
процессе бэкенда копятся незакрытые сессии. Синхронный клиент живёт внутри одного
вызова, а поток отдаёт event loop обратно на время сетевого запроса.

Ошибки ccxt переводятся в доменные исключения так, чтобы «ключ негодный» (400) и
«биржа не ответила» (503) не смешивались: во втором случае пользователю нельзя
говорить, что его ключ неверен.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import ccxt

from src.core.exceptions import BadRequestError, ServiceUnavailableError

logger = logging.getLogger(__name__)

# Биржа в конфиге бота ровно одна: templates/config.template.json всегда пишет
# "name": "bybit". Ключ другой биржи сохранять нельзя — он молча уехал бы в
# bybit-конфиг, и бот всё равно бы не заработал.
SUPPORTED_EXCHANGES = ("bybit",)

# Секунды в мс. POST на добавление ключа ждёт этот вызов синхронно, минуту висеть нельзя.
REQUEST_TIMEOUT_MS = 10_000

# Группы прав Bybit, любая из которых означает «ключ может торговать фьючерсами».
# Список именно такой, потому что состав групп в ответе /v5/user/query-api различается
# для UTA и классического аккаунта, и проверка одной жёстко заданной группы отбивала бы
# рабочие ключи.
_FUTURES_PERMISSION_GROUPS = ("ContractTrade", "Derivatives", "UnifiedTrading")

# За сколько до истечения ключа писать предупреждение в лог (отказывать — рано).
_EXPIRY_WARNING = timedelta(days=7)


@dataclass(frozen=True)
class AccountBalance:
    """Кошелёк ключа в USDT.

    total — весь капитал (включая занятое под открытые позиции и нереализованный PnL),
    free — свободное прямо сейчас. Капитал под нового бота считается от total,
    см. capital_guard: депозит уже торгующего бота биржа из free вычла сама.
    """

    total: float
    free: float


@dataclass(frozen=True)
class KeyPermissions:
    """Что позволено ключу. expires_at=None — бессрочный ключ."""

    read_only: bool
    can_trade_futures: bool
    expires_at: datetime | None


class ExchangeAccountClient:
    """Порт к бирже. Реализация — CcxtAccountClient, в тестах вместо неё фейк."""

    async def fetch_balance(self, exchange: str, key: str, secret: str) -> AccountBalance:
        raise NotImplementedError

    async def fetch_permissions(self, exchange: str, key: str, secret: str) -> KeyPermissions:
        raise NotImplementedError


def ensure_supported_exchange(exchange: str) -> str:
    """Нормализует название биржи и отбивает всё, кроме поддерживаемого."""
    normalized = (exchange or "").strip().lower()
    if normalized not in SUPPORTED_EXCHANGES:
        raise BadRequestError("Пока поддерживается только Bybit — ключ другой биржи сервис использовать не сможет.")
    return normalized


def _translate(exc: Exception) -> Exception:
    """Ошибка ccxt -> доменное исключение.

    Порядок веток повторяет иерархию ccxt и менять его нельзя: PermissionDenied
    наследует AuthenticationError, а RateLimitExceeded, RequestTimeout и
    ExchangeNotAvailable — все NetworkError.
    """
    if isinstance(exc, ccxt.PermissionDenied):
        return BadRequestError(
            "Биржа отклонила ключ: недостаточно прав или запрос пришёл с IP, которого нет в белом списке ключа."
        )
    if isinstance(exc, ccxt.AuthenticationError):
        return BadRequestError("Биржа отклонила ключ: неверный API key или secret (либо срок его действия истёк).")
    if isinstance(exc, ccxt.NetworkError):
        # Сюда же попадают таймаут и rate limit. Это не приговор ключу, и говорить
        # пользователю «ключ неверный» здесь было бы прямой ложью.
        return ServiceUnavailableError("Биржа сейчас не отвечает. Ключ не сохранён — попробуйте ещё раз через минуту.")
    if isinstance(exc, ccxt.ExchangeError):
        return BadRequestError(f"Биржа отклонила ключ: {str(exc)[:200]}")
    return ServiceUnavailableError("Не удалось связаться с биржей. Попробуйте ещё раз через минуту.")


class CcxtAccountClient(ExchangeAccountClient):
    """Реальный клиент. Каждый вызов создаёт свой экземпляр ccxt и закрывает его."""

    def _build(self, exchange: str, key: str, secret: str):
        exchange_class = getattr(ccxt, exchange)
        return exchange_class(
            {
                "apiKey": key,
                "secret": secret,
                "timeout": REQUEST_TIMEOUT_MS,
                "enableRateLimit": True,
                # Тот же кошелёк, из которого торгует freqtrade: в шаблоне конфига
                # trading_mode=futures, margin_mode=isolated. Со спотового счёта
                # проверка капитала считала бы чужие деньги.
                "options": {"defaultType": "swap"},
            }
        )

    async def fetch_balance(self, exchange: str, key: str, secret: str) -> AccountBalance:
        return await asyncio.to_thread(self._fetch_balance_sync, exchange, key, secret)

    def _fetch_balance_sync(self, exchange: str, key: str, secret: str) -> AccountBalance:
        client = self._build(exchange, key, secret)
        try:
            raw = client.fetch_balance()
        except Exception as exc:
            raise _translate(exc) from exc
        finally:
            client.close()

        usdt = raw.get("USDT") or {}
        # Пустой кошелёк — это ноль, а не ошибка: ключ рабочий, денег на нём нет.
        return AccountBalance(total=float(usdt.get("total") or 0.0), free=float(usdt.get("free") or 0.0))

    async def fetch_permissions(self, exchange: str, key: str, secret: str) -> KeyPermissions:
        return await asyncio.to_thread(self._fetch_permissions_sync, exchange, key, secret)

    def _fetch_permissions_sync(self, exchange: str, key: str, secret: str) -> KeyPermissions:
        client = self._build(exchange, key, secret)
        try:
            raw = client.privateGetV5UserQueryApi()
        except Exception as exc:
            raise _translate(exc) from exc
        finally:
            client.close()

        return parse_bybit_permissions(raw)


def parse_bybit_permissions(raw: dict) -> KeyPermissions:
    """Разбирает ответ Bybit /v5/user/query-api.

    Функция отдельная и чистая, чтобы её можно было проверить тестом без сети.

    Неизвестный формат ответа трактуется в пользу ключа (read_only=False,
    can_trade_futures=True): состав групп прав у Bybit различается между UTA и
    классическим аккаунтом, и ошибка разбора не должна отбивать рабочий ключ.
    Явное readOnly=1 — единственный жёсткий сигнал, ему верим всегда.
    """
    result = raw.get("result") if isinstance(raw, dict) else None
    if not isinstance(result, dict):
        logger.warning("Unexpected permissions payload from exchange", extra={"payload_type": type(raw).__name__})
        return KeyPermissions(read_only=False, can_trade_futures=True, expires_at=None)

    read_only = str(result.get("readOnly", "0")) == "1"

    permissions = result.get("permissions")
    if isinstance(permissions, dict):
        can_trade_futures = any(permissions.get(group) for group in _FUTURES_PERMISSION_GROUPS)
    else:
        can_trade_futures = True

    return KeyPermissions(read_only=read_only, can_trade_futures=can_trade_futures, expires_at=_parse_expiry(result))


def _parse_expiry(result: dict) -> datetime | None:
    """expiredAt приходит строкой ISO; у бессрочного ключа поля нет или оно пустое."""
    value = result.get("expiredAt")
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Could not parse API key expiry", extra={"expired_at": str(value)[:50]})
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


async def verify_key(client: ExchangeAccountClient, exchange: str, key: str, secret: str) -> AccountBalance:
    """
    Полная проверка ключа перед сохранением. Возвращает баланс, если ключ годен.

    Проверок три, и все три ловят разные реальные отказы:
      * права ключа — read-only ключ прекрасно отдаёт баланс, но не откроет ни одной
        сделки; без этой проверки задача решалась бы наполовину;
      * срок действия — ключ Bybit можно выпустить с датой окончания;
      * баланс — заодно доказывает, что ключ вообще работает на этом счёте.

    Ошибка сети поднимается наружу как ServiceUnavailableError и ключ не сохраняется:
    непроверенный ключ в базе — ровно то состояние, которое здесь и убирается.
    """
    permissions = await client.fetch_permissions(exchange, key, secret)

    if permissions.read_only:
        raise BadRequestError(
            "Этот ключ работает только на чтение — бот не сможет открывать сделки. "
            "Создайте на бирже ключ с правом торговли деривативами."
        )
    if not permissions.can_trade_futures:
        raise BadRequestError(
            "У ключа нет прав на торговлю деривативами (фьючерсами). "
            "Отметьте это право в настройках ключа на бирже и добавьте его заново."
        )

    now = datetime.now(UTC)
    if permissions.expires_at is not None:
        if permissions.expires_at <= now:
            raise BadRequestError("Срок действия ключа истёк — выпустите на бирже новый.")
        if permissions.expires_at - now <= _EXPIRY_WARNING:
            logger.warning("API key expires soon", extra={"expires_at": permissions.expires_at.isoformat()})

    balance = await client.fetch_balance(exchange, key, secret)
    logger.info(
        "API key verified on exchange",
        extra={"exchange": exchange, "balance_total": balance.total, "balance_free": balance.free},
    )
    return balance
