from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.trade import Trade


class TradeRepository:
    """
    Методы возвращают готовые списки, а не Select.

    Раньше get_*_trades отдавали недостроенный select(), а StatsService сам доклеивал
    .where()/.order_by() и выполнял запрос через repo.db. Из-за этого фильтр по периоду
    и сортировка разъехались между двумя вызовами: у статистики по боту сортировка была,
    у портфеля — нет, и график с просадкой считались по случайному порядку строк.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_trade(self, bot_id: str, ft_id: int) -> Trade | None:
        result = await self.db.execute(
            select(Trade).where(Trade.bot_id == bot_id, Trade.freqtrade_trade_id == ft_id)
        )
        return result.scalar_one_or_none()

    async def get_closed_trades(
        self,
        user_id: int,
        *,
        bot_id: str | None = None,
        since: datetime | None = None,
    ) -> list[Trade]:
        """
        Закрытые сделки пользователя, отсортированные по времени закрытия.

        Сортировка — часть контракта, а не удобство: _build_pnl_chart и _max_drawdown
        идут по списку подряд и копят P&L, поэтому на неотсортированном списке они молча
        дадут неверный график и неверную просадку.

        bot_id — сузить до одного бота, since — отсечь всё, что закрыто раньше.
        """
        query = select(Trade).where(
            Trade.user_id == user_id,
            Trade.close_time.isnot(None),
        )
        if bot_id is not None:
            query = query.where(Trade.bot_id == bot_id)
        if since is not None:
            query = query.where(Trade.close_time >= since)

        query = query.order_by(Trade.close_time.asc())

        result = await self.db.execute(query)
        return list(result.scalars().all())
