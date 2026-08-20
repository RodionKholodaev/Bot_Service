from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.bot import Bot
from src.models.user import User


class BotRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, bot: Bot) -> Bot:
        self.db.add(bot)
        await self.db.flush()
        await self.db.refresh(bot)
        return bot

    async def get_all_active_bots(self):
        bots = await self.db.execute(select(Bot).where(Bot.status == "running", Bot.is_active.is_(True)))
        running_bots = bots.scalars().all()
        return running_bots

    async def get_user(self, bot_user_id):  # это недоразумение нужно убрать
        user = await self.db.execute(select(User).where(User.id == bot_user_id))
        return user.scalar_one_or_none()

    async def get_bot_by_id(self, bot_id):
        result = await self.db.execute(select(Bot).where(Bot.id == bot_id))
        return result.scalar_one_or_none()

    async def get_all_busy_ports(self):
        # Только активные боты: у архивированного контейнер удалён, порт на хосте
        # свободен, и держать его занятым навсегда — значит рано или поздно исчерпать
        # весь диапазон BOT_API_PORT_RANGE.
        result = await self.db.execute(select(Bot.api_port).where(Bot.is_active.is_(True)))
        return result.scalars().all()

    async def allocate_port(self) -> int | None:
        """
        Выдаёт первый свободный порт из диапазона
        """
        used = await BotRepository(self.db).get_all_busy_ports()
        for port in range(settings.BOT_API_PORT_RANGE_START, settings.BOT_API_PORT_RANGE_END + 1):
            if port not in used:
                return port
        return None

    async def get_user_active_bots(self, user_id):
        result = await self.db.execute(select(Bot).where(Bot.user_id == user_id, Bot.is_active.is_(True)))
        bots = result.scalars().all()
        return bots

    async def get_user_bots(self, user_id):
        """Все боты пользователя, включая архивированные — нужны там, где считается
        статистика за всё время (иначе прибыль удалённых ботов исчезает задним числом)."""
        result = await self.db.execute(select(Bot).where(Bot.user_id == user_id))
        return result.scalars().all()

    async def change_bot_status(
        self, status: Literal["created", "starting", "running", "stopped", "error"], bot: Bot
    ) -> Bot:
        bot.status = status
        await self.db.flush()
        await self.db.refresh(bot)
        return bot

    async def add_error_message(self, error: str, bot: Bot):
        bot.error_message = error
        await self.db.flush()
        await self.db.refresh(bot)
        return bot

    async def change_container_id(self, container_id, bot: Bot):
        bot.container_id = container_id
        await self.db.flush()
        await self.db.refresh(bot)
        return bot

    async def archive_bot(self, bot: Bot) -> Bot:
        """
        Мягкое удаление. Физического DELETE тут намеренно нет: у trades.bot_id стоит
        ondelete="CASCADE", и удаление бота уносило бы вместе с ним всю его историю
        сделок — общий P&L, winrate и график пользователя менялись бы задним числом.
        """
        bot.is_active = False
        # контейнера у архивированного бота уже нет, "running" был бы враньём
        bot.status = "stopped"
        await self.db.flush()
        await self.db.refresh(bot)
        return bot
