"""
LT-4: как /stats/portfolio деградирует от объёма сделок.

get_portfolio_stats тянет все закрытые сделки пользователя за период и считает
график P&L и просадку в питоне — то есть это и тяжёлый SELECT, и CPU в event loop.

Прогон делается по одному разу на каждый объём данных: 1k, 10k, 100k сделок
(loadtests/seed_trades.py), и цифры сравниваются между собой. Период задаётся
через LT4_PERIOD: "all" — весь объём, "1W" — проверка, что фильтр по датам
реально сокращает работу (если разницы нет, фильтруется не там, где кажется).

Запуск:
  python loadtests/seed_trades.py 10000
  locust -f loadtests/lt4_stats.py --host http://127.0.0.1:8000 --web-host 127.0.0.1
"""

import os

from locust import HttpUser, constant, task

EMAIL = os.getenv("LT_EMAIL", "loadtest@example.com")
PASSWORD = os.getenv("LT_PASSWORD", "loadtest-password-123")  # noqa: S105
PERIOD = os.getenv("LT4_PERIOD", "all")


class StatsUser(HttpUser):
    wait_time = constant(0)

    def on_start(self):
        # См. seed_user.py: системный прокси Windows иначе перехватит localhost.
        self.client.trust_env = False
        resp = self.client.post(
            "/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
            name="[setup] login",
        )
        self.headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    @task
    def portfolio(self):
        with self.client.get(
            f"/stats/portfolio?period={PERIOD}",
            headers=self.headers,
            name=f"GET /stats/portfolio [{PERIOD}]",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"ожидали 200, получили {resp.status_code}")
