"""
Наполняет БД закрытыми сделками для LT-4.

Работает не через API (такой ручки нет), а прямо через модели: находит
пользователя по email, заводит ему бота и вставляет N закрытых сделок,
разбросанных по последним 180 дням.

Запуск (из backend/):  python loadtests/seed_trades.py 10000
"""

import asyncio
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os  # noqa: E402

from sqlalchemy import select  # noqa: E402

from src.database import AsyncSessionLocal  # noqa: E402
from src.models.bot import Bot  # noqa: E402

# Импортируется ради FK bots.api_key_id: без зарегистрированной модели
# SQLAlchemy не может разрешить ссылку и падает на первом же запросе.
from src.models.exchange_api_key import ExchangeApiKey  # noqa: E402,F401
from src.models.trade import Trade  # noqa: E402
from src.models.user import User  # noqa: E402

EMAIL = os.getenv("LT_EMAIL", "loadtest@example.com")
COUNT = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000
BATCH = 1000


def _make_bot(user_id: int) -> Bot:
    """Бот-владелец сделок. dry_run, без api_key_id — в докер не поедет."""
    bot_id = str(uuid.uuid4())
    return Bot(
        id=bot_id,
        user_id=user_id,
        name=f"LT-4 {bot_id[:8]}",
        pair="BTC/USDT:USDT",
        leverage=5,
        direction="long",
        tradable_balance_ratio=0.2,
        stake_amount=1000.0,
        strategy_preset="moderate",
        entry_filters_long=[],
        entry_filters_short=[],
        take_profit={"0": 0.04},
        stop_loss=-0.1,
        dry_run=True,
        container_name=f"lt4-{bot_id[:8]}",
        api_port=0,
        api_username="lt4",
        api_password="lt4",  # noqa: S106
        status="stopped",
    )


def _make_trade(bot: Bot, index: int, opened: datetime) -> Trade:
    profit = round(random.uniform(-30, 45), 2)  # noqa: S311 — это генератор данных, не крипта
    return Trade(
        bot_id=bot.id,
        user_id=bot.user_id,
        freqtrade_trade_id=index,
        pair=bot.pair,
        direction="long",
        open_rate=60000.0,
        close_rate=60000.0 + profit,
        amount=0.01,
        leverage=bot.leverage,
        profit_usdt=profit,
        profit_pct=profit / 1000 * 100,
        open_time=opened,
        close_time=opened + timedelta(minutes=30),
    )


async def main() -> int:
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == EMAIL))).scalar_one_or_none()
        if user is None:
            print(f"Нет пользователя {EMAIL}. Сначала: python loadtests/seed_user.py")
            return 1

        bot = _make_bot(user.id)
        db.add(bot)
        await db.flush()

        now = datetime.now(UTC)
        for start in range(0, COUNT, BATCH):
            # Сделки размазаны по 180 дням, чтобы фильтр по периоду в /stats
            # реально что-то отсекал, а не выбирал всё подряд.
            db.add_all(
                [
                    _make_trade(bot, i, now - timedelta(minutes=180 * 24 * 60 * i // max(COUNT, 1)))
                    for i in range(start, min(start + BATCH, COUNT))
                ]
            )
            await db.commit()
            print(f"  вставлено {min(start + BATCH, COUNT)} / {COUNT}")

    print(f"Готово: бот {bot.id}, сделок {COUNT}, владелец {EMAIL}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
