import os

from locust import HttpUser, constant, task

EMAIL = os.getenv("LT_EMAIL", "loadtest@example.com")
PASSWORD = os.getenv("LT_PASSWORD", "loadtest-password-123")  # noqa: S105
PERIOD = os.getenv("LT4_PERIOD", "all")


class StatsUser(HttpUser):
    wait_time = constant(0)

    def on_start(self):
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
