import ipaddress as ip
import logging

from fastapi import Request

logger = logging.getLogger(__name__)


def get_ip(request: Request) -> ip.IPv4Address | ip.IPv6Address | None:
    """IP клиента запроса. None — если определить его не удалось.

    Берём ПОСЛЕДНИЙ элемент X-Forwarded-For, а не первый. Заголовок целиком
    контролируется клиентом, а стандартный nginx
    (``proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for``) не
    перезаписывает его, а дописывает реальный адрес в конец. Значит первый
    элемент — это то, что прислал сам клиент: раньше по нему можно было
    выдать себя за ЮKassa и подтвердить чужой платёж. Последний элемент
    добавляет наш собственный прокси.

    Схема работает и при ``proxy_set_header X-Forwarded-For $remote_addr``:
    там в заголовке ровно один адрес, первый и последний совпадают.
    Важно: приложение должно быть доступно ТОЛЬКО через прокси, иначе
    заголовок целиком подделывает кто угодно.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")

    if forwarded_for:
        raw = forwarded_for.split(",")[-1].strip()
        source = "X-Forwarded-For"
    elif request.client is not None:
        # прокси нет — доверяем адресу самого соединения
        raw = request.client.host
        source = "connection"
    else:
        logger.warning("Client IP is unavailable: no X-Forwarded-For and no client in scope")
        return None

    try:
        client_ip = ip.ip_address(raw)
    except ValueError:
        # мусор в заголовке — не 500, а «адрес неизвестен»: вызывающий решит,
        # что с этим делать (для вебхука это отказ)
        logger.warning(
            "Failed to parse client IP",
            extra={"raw_value": raw[:100], "source": source},
        )
        return None

    logger.debug(
        "Client IP resolved",
        extra={"client_ip": str(client_ip), "source": source},
    )
    return client_ip
