"""
Готовит пользователя для нагрузочных сценариев и проверяет, что им можно залогиниться.

Отдельный шаг, а не создание на лету внутри locust: LT-1 меряет стоимость bcrypt на
проверке пароля, и регистрация (а это ещё один bcrypt, уже на хешировании) внутри
замера смазала бы картину.

Проверка логина в конце — не формальность. В AuthService.login стоит короткое
замыкание `if not user or not verify_password(...)`: с несуществующим email
verify_password не вызывается вообще, запрос становится копеечным, и нагрузочный
тест померяет пустоту, показав сотни RPS. Поэтому убеждаемся, что ответ 200,
до того, как запускать locust.

Запуск (из backend/):  python loadtests/seed_user.py
"""

import os
import sys

import httpx

HOST = os.getenv("LT_HOST", "http://127.0.0.1:8000")
EMAIL = os.getenv("LT_EMAIL", "loadtest@example.com")
PASSWORD = os.getenv("LT_PASSWORD", "loadtest-password-123")  # noqa: S105
USERNAME = os.getenv("LT_USERNAME", "loadtest")

# Обязательных согласий три: CROSS_BORDER_TRANSFER в src/core/legal.py == True,
# и AuthService._collect_consents отбивает регистрацию 400-м без любого из них.
REGISTER_BODY = {
    "username": USERNAME,
    "email": EMAIL,
    "password": PASSWORD,
    "accept_terms": True,
    "accept_pdn": True,
    "accept_cross_border": True,
}


def main() -> int:

    with httpx.Client(base_url=HOST, timeout=30.0, trust_env=False) as client:
        try:
            resp = client.post("/auth/register", json=REGISTER_BODY)
        except httpx.ConnectError:
            print(f"Не достучались до {HOST}. Бэкенд запущен?")
            return 1

        if resp.status_code == 201:
            print(f"Пользователь создан: {EMAIL}")
        elif resp.status_code == 409:
            print(f"Пользователь уже есть, переиспользуем: {EMAIL}")
        else:
            print(f"Регистрация не удалась: {resp.status_code} {resp.text}")
            return 1

        # Контрольный логин тем же телом, что будет слать locust.
        login = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
        if login.status_code != 200:
            print(f"Логин не прошёл: {login.status_code} {login.text}")
            return 1

    print(f"Логин отвечает 200. Можно запускать locust против {HOST}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
