import ipaddress as ip
import logging

from fastapi import Request

logger = logging.getLogger(__name__)


def get_ip(request: Request):
    # получаем ip из заголовка nginx
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # если он есть, то есть nginx
        client_ip = ip.ip_address(forwarded_for.split(",")[0].strip())
        logger.debug(
            "Client IP resolved from X-Forwarded-For header",
            extra={"client_ip": str(client_ip), "header": forwarded_for},
        )
    else:
        # если nginx нет
        client_ip = ip.ip_address(request.client.host)  # type: ignore
        logger.debug(
            "Client IP resolved from direct connection",
            extra={"client_ip": str(client_ip)},
        )

    return client_ip


"""
важно: в настройках nginx нужно убирать заголовок X-Forwarded-For из запросов!!!
"""
