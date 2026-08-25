"""
Юнит-тесты get_ip — определения адреса клиента за прокси.

Функция чистая: ни БД, ни сети, только объект запроса, поэтому вместо настоящего
starlette Request подсовывается FakeRequest с нужными заголовками.

Главное, что здесь зафиксировано: из X-Forwarded-For берётся ПОСЛЕДНИЙ адрес.
Заголовок пишет клиент, а стандартный nginx лишь дописывает реальный адрес в
конец — значит первый элемент подделывается кем угодно. По нему раньше можно
было выдать себя за ЮKassa и подтвердить чужой платёж (см. payment_service).
"""

import ipaddress

import pytest

from src.services.get_ip import get_ip


class FakeClient:
    """Fake вместо request.client — адрес самого TCP-соединения."""

    def __init__(self, host: str):
        self.host = host


class FakeRequest:
    """Fake вместо starlette Request — get_ip читает только headers и client."""

    def __init__(self, *, forwarded_for: str | None = None, client_host: str | None = "10.0.0.1"):
        self.headers = {"X-Forwarded-For": forwarded_for} if forwarded_for else {}
        self.client = FakeClient(client_host) if client_host else None


def test_forwarded_for_takes_the_last_address():
    # Arrange
    # так выглядит заголовок при $proxy_add_x_forwarded_for: сначала то, что прислал
    # клиент (здесь — подделка под ЮKassa), в конце — адрес, добавленный нашим nginx
    request = FakeRequest(forwarded_for="185.71.76.1, 203.0.113.9")

    # Act
    result = get_ip(request)  # type: ignore[arg-type]

    # Assert
    assert result == ipaddress.ip_address("203.0.113.9")


def test_single_forwarded_for_address_is_used_as_is():
    # Arrange
    # вариант с proxy_set_header X-Forwarded-For $remote_addr — адрес ровно один
    request = FakeRequest(forwarded_for="203.0.113.9")

    # Act
    result = get_ip(request)  # type: ignore[arg-type]

    # Assert
    assert result == ipaddress.ip_address("203.0.113.9")


def test_connection_address_is_used_without_proxy_header():
    # Arrange
    request = FakeRequest(client_host="192.168.1.5")

    # Act
    result = get_ip(request)  # type: ignore[arg-type]

    # Assert
    assert result == ipaddress.ip_address("192.168.1.5")


@pytest.mark.parametrize("garbage", ["not-an-ip", "", "999.999.999.999"])
def test_unparsable_address_returns_none(garbage):
    # Arrange
    # мусор в заголовке — это отказ, а не 500: раньше ip_address() бросал ValueError
    request = FakeRequest(forwarded_for=f"1.2.3.4, {garbage}", client_host=None)

    # Act
    result = get_ip(request)  # type: ignore[arg-type]

    # Assert
    assert result is None


def test_request_without_client_returns_none():
    # Arrange
    request = FakeRequest(client_host=None)

    # Act
    result = get_ip(request)  # type: ignore[arg-type]

    # Assert
    assert result is None
