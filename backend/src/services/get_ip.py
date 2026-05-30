from fastapi import Request
import ipaddress as ip

def get_ip(request: Request):
    # получаем ip из заголовка nginx
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # если он есть, то есть nginx
        client_ip = ip.ip_address(forwarded_for.split(",")[0].strip())
    else:
        # если nginx нет
        client_ip = ip.ip_address(request.client.host)  # type: ignore

    return client_ip
"""
важно: в настройках nginx нужно убирать заголовок X-Forwarded-For из запросов!!!
"""