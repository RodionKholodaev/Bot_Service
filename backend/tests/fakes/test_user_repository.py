from src.models.user import User

class FakeUserRepository:
    def __init__(self):
        self.users = {}
        self.counter = 1

    async def email_exists(self, email: str) -> bool:
        return any(u.email == email for u in self.users.values())

    async def get_user(self, email: str):
        for u in self.users.values():
            if u.email == email:
                return u
        return None

    async def get_user_by_id(self, user_id: int):
        return self.users.get(user_id)

    async def create_user(self, user: User):
        user.id = self.counter
        self.counter += 1
        self.users[user.id] = user
        return user

    async def change_balance(self, user: User, amount: float):
        user.service_balance += amount