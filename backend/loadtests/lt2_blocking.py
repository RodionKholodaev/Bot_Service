"""
LT-2: как тяжёлая ручка роняет латентность посторонних запросов.

Идея: два класса пользователей в одном прогоне.
  BackgroundUser — 1 штука, дёргает дешёвую ручку с фиксированной частотой.
  LoginAttacker  — N штук, долбит /auth/login (bcrypt блокирует event loop),
                   стартует не сразу, а через ATTACK_DELAY секунд.

Смотрим на p95 строки "GET /bots/presets" до и после старта атаки: сама ручка
не изменилась, но встала в общую очередь за event loop.

Запуск (users = 1 фоновый + attackers, они разведены через fixed_count):
  locust -f loadtests/lt2_blocking.py --host http://127.0.0.1:8000 --web-host 127.0.0.1
"""

import os

import gevent
from locust import HttpUser, constant, constant_throughput, task

EMAIL = os.getenv("LT_EMAIL", "loadtest@example.com")
PASSWORD = os.getenv("LT_PASSWORD", "loadtest-password-123")  # noqa: S105

# Через сколько секунд после старта прогона включается нагрузка на логин.
ATTACK_DELAY = float(os.getenv("LT2_ATTACK_DELAY", "30"))
# Сколько запросов в секунду держит фоновый пользователь.
BACKGROUND_RPS = float(os.getenv("LT2_BACKGROUND_RPS", "2"))


def _no_proxy(user):
    # См. seed_user.py: системный прокси Windows иначе перехватит localhost.
    user.client.trust_env = False


class BackgroundUser(HttpUser):
    """Невиновный запрос: лёгкая авторизованная ручка, читает словарь в памяти."""

    # Ровно один такой пользователь, сколько бы ни задали -u.
    fixed_count = 1
    # constant_throughput, а не constant(0): частота держится независимо от того,
    # насколько медленно отвечает сервис — иначе фоновая нагрузка сама бы
    # подстроилась под тормоза и деградация оказалась бы не видна.
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

    def on_start(self):
        _no_proxy(self)
        # Пауза перед началом атаки: нужен кусок графика "как было до".
        gevent.sleep(ATTACK_DELAY)

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
