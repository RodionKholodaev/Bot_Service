from src.models.bot import Bot
from src.models.user import User
from src.models.trade import Trade
from src.services.exchange_rate_service import ExchangeRateService
import logging
logger = logging.getLogger(__name__)
class CommissionService:
    @staticmethod
    async def process_commission(trade: Trade, user: User, bot: Bot):
        """
        Вызывается один раз при закрытии сделки:
        - обновляет Bot.total_profit
        - рассчитывает и списывает комиссию сервиса
        """
        profit = trade.profit_usdt or 0.0

        # Обновляем накопленный профит бота
        bot.total_profit = round(bot.total_profit + profit, 8)

        # Комиссия — только с прибыльных сделок
        if profit > 0 and not trade.commission_paid:
            rate_service = ExchangeRateService()
            current_rate = await rate_service.get_usdt_rub()
            if current_rate is None: raise ValueError("Не удалось получить курс USDT")

            commission_usdt = round(profit * user.commission_rate, 8) 
            commission_rub = round(profit * user.commission_rate, 8) * current_rate

            trade.commission_usdt = commission_usdt
            trade.commission_rub = commission_rub
            trade.commission_paid = True

            # Списываем с сервисного баланса пользователя
            user.service_balance = round(user.service_balance - commission_rub, 8)

            # Суммарно списанная комиссия по боту (не гибкий код!!!!)
            bot.total_commission_paid_usdt = round(bot.total_commission_paid_usdt + commission_usdt, 8)
            bot.total_commission_paid_rub = round(bot.total_commission_paid_rub + commission_rub, 8)

            logger.info(
                "Bot %s trade #%s closed: profit=%.4f USDT, commission=%.4f USDT",
                bot.id, trade.freqtrade_trade_id, profit, commission_usdt,
            )
