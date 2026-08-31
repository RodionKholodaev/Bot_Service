import os

from locust import HttpUser, constant, task

EMAIL = os.getenv("LT_EMAIL", "loadtest@example.com")
PASSWORD = os.getenv("LT_PASSWORD", "loadtest-password-123")  # noqa: S105


class LoginUser(HttpUser):
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
                # Явно валим прогон: молчаливые 4xx/5xx превратили бы замер
                # стоимости bcrypt в замер стоимости отказа.
                resp.failure(f"ожидали 200, получили {resp.status_code}: {resp.text[:200]}")
