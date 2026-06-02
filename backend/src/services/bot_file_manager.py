from pathlib import Path
from src.config import settings
from src.models.bot import Bot
from src.services.freqtrade_config import generate_config, write_config
from src.services.freqtrade_strategy import generate_strategy_file, write_strategy_file
import shutil
import logging
logger = logging.getLogger(__name__)
class BotFileManager:
    
    @staticmethod
    def _bot_dir(bot_id: str) -> Path:
        return settings.BOTS_DATA_DIR / bot_id

    @staticmethod
    async def materialize_bot_files(bot: Bot, user_id: int, api_key, api_secret, iternal_api_port, jwt_secret, ws_token) -> None:
        # создаем папку для бота
        bot_dir = BotFileManager._bot_dir(bot.id)
        bot_dir.mkdir(parents=True, exist_ok=True)
        (bot_dir / "user_data" / "strategies").mkdir(parents=True, exist_ok=True)
        (bot_dir / "user_data" / "logs").mkdir(parents=True, exist_ok=True)
        (bot_dir / "user_data" / "data").mkdir(parents=True, exist_ok=True)

        # генерация конфига
        cfg = await generate_config(
            pair=bot.pair,
            api_port_inside_container=iternal_api_port,
            jwt_secret=jwt_secret,
            ws_token=ws_token,
            api_username=bot.api_username,
            api_password=bot.api_password,
            dry_run=bot.dry_run,
            exchange_key=api_key,
            exchange_secret=api_secret,
            stake_amount = bot.stake_amount,
            tradable_balance_ratio=bot.tradable_balance_ratio,
            user_id = user_id
        )

        # записываем его в файл
        write_config(cfg, bot_dir / "config.json")

        # создаем файл стратегии
        can_short = bot.direction in ("short", "both")
        strategy_code = generate_strategy_file(
            leverage=bot.leverage,
            can_short=can_short,
            entry_filters_long=list(bot.entry_filters_long or []),
            entry_filters_short=list(bot.entry_filters_short or []),
            take_profit=dict(bot.take_profit),
            stoploss=bot.stop_loss,
            trailing_stop=bot.trailing_stop,
        )
        # сохраняем файл стратегии
        write_strategy_file(
            strategy_code,
            bot_dir / "user_data" / "strategies" / "MultiFilterStrategy.py",
        )

    @staticmethod
    def cleanup_bot_files(bot_id: str) -> None:
        bot_dir = BotFileManager._bot_dir(bot_id)
        if bot_dir.exists():
            try:
                shutil.rmtree(bot_dir)
            except Exception:
                logger.exception(f"Не удалось удалить папку бота {bot_dir}")