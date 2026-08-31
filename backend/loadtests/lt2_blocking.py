import os

import gevent
from locust import HttpUser, constant, constant_throughput, task

EMAIL = os.getenv("LT_EMAIL", "loadtest@example.com")
PASSWORD = os.getenv("LT_PASSWORD", "loadtest-password-123")  # noqa: S105

# Через сколько секунд после старта прогона включается нагрузка на логин.
ATTACK_DELAY = float(os.getenv("LT2_ATTACK_DELAY", "30"))
# Сколько запросов в секунду держит фоновый пользователь.
BACKGROUND_RPS = float(os.getenv("LT2_BACKGROUND_RPS", "2"))


class BackgroundUser(HttpUser):
    """Невиновный запрос: лёгкая авторизованная ручка, читает словарь в памяти."""

    fixed_count = 1

    wait_time = constant_throughput(BACKGROUND_RPS)

    def on_start(self):
        _no_proxy(self)
        # Один логин ради токена — он вне замера, у него своё имя в статистике.
        resp = self.client.post(
            "/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
            name="[setup] login",
        )
        self.headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    @task
    def presets(self):
        with self.client.get(
            "/bots/presets",
            headers=self.headers,
            name="GET /bots/presets",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"ожидали 200, получили {resp.status_code}")


class LoginAttacker(HttpUser):
    """Нагрузка, ради которой всё затевалось: bcrypt в event loop."""

    fixed_count = int(os.getenv("LT2_ATTACKERS", "10"))
    wait_time = constant(0)


    @task
    def login(self):
        with self.client.post(
            "/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
            name="POST /auth/login",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"ожидали 200, получили {resp.status_code}")
