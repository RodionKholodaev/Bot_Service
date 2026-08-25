import logging

from src.models.bot import Bot
from src.models.trade import Trade
from src.models.user import User
from src.services.exchange_rate_service import ExchangeRateService

logger = logging.getLogger(__name__)


class CommissionService:
    @staticmethod
    async def process_commission(trade: Trade, user: User, bot: Bot):
        """
        Вызывается один раз при закрытии сделки:
        - обновляет Bot.total_profit
        - рассчитывает и списывает комиссию сервиса

        Идемпотентна: trade.commission_paid означает "сделка уже учтена" и ставится
        в том числе на убыточных сделках. Раньше флаг ставился только на прибыльных,
        а bot.total_profit прибавлялся вообще без проверки — при повторном вызове
        (например, если у закрытой сделки не разобралась дата закрытия и воркер каждый
        цикл считал её только что закрывшейся) профит бота накручивался бесконечно.
        """
        if trade.commission_paid:
            logger.warning(
                "Trade already processed, skipping",
                extra={"bot_id": bot.id, "trade_id": trade.freqtrade_trade_id},
            )
            return

        profit = trade.profit_usdt or 0.0

        # Обновляем накопленный профит бота
        bot.total_profit = round(bot.total_profit + profit, 8)

        # Комиссия — только с прибыльных сделок и только у боевых ботов. В dry_run
        # прибыли не существует: сделки виртуальные, денег на бирже нет, и брать за них
        # реальные рубли нельзя. Проверка стоит до запроса курса — иначе тестовый бот
        # ещё и ходил бы в сеть на каждой прибыльной сделке, а недоступный курс ронял
        # бы синхронизацию сделок исключением ниже.
        if profit > 0 and bot.dry_run:
            logger.info(
                "Dry-run bot closed profitable deal, commission not charged",
                extra={
                    "bot_id": bot.id,
                    "trade_id": trade.freqtrade_trade_id,
                    "profit": profit,
                },
            )
        elif profit > 0:
            rate_service = ExchangeRateService()
            current_rate = await rate_service.get_usdt_rub()
            # Курс не получен — сделку не учитываем вовсе: исключение откатит транзакцию
            # целиком (вместе с bot.total_profit выше), и следующий цикл воркера повторит
            # обработку. Поэтому флаг ставится строго после успешного расчёта.
            if current_rate is None:
                raise ValueError("Не удалось получить курс USDT")

            commission_usdt = round(profit * user.commission_rate, 8)
            commission_rub = round(profit * user.commission_rate, 8) * current_rate

            trade.commission_usdt = commission_usdt
            trade.commission_rub = commission_rub
            # Курс фиксируем в самой сделке: списание в рублях иначе нечем подтвердить —
            # ExchangeRateService отдаёт текущий курс, и задним числом уже не узнать,
            # по какому именно посчитаны эти commission_rub.
            trade.exchange_rate_rub_usdt = current_rate

            # Списываем с сервисного баланса пользователя
            user.service_balance = round(user.service_balance - commission_rub, 8)

            # Суммарно списанная комиссия по боту (не гибкий код!!!!)
            bot.total_commission_paid_usdt = round(bot.total_commission_paid_usdt + commission_usdt, 8)
            bot.total_commission_paid_rub = round(bot.total_commission_paid_rub + commission_rub, 8)

            logger.info(
                "Bot closed profitable deal",
                extra={
                    "bot_id": bot.id,
                    "trade_id": trade.freqtrade_trade_id,
                    "profit": profit,
                    "commission_usdt": commission_usdt,
                },
            )
        elif profit < 0:
            logger.info(
                "Bot closed unprofitable deal",
                extra={
                    "bot_id": bot.id,
                    "trade_id": trade.freqtrade_trade_id,
                    "profit": profit,
                },
            )

        trade.commission_paid = True
