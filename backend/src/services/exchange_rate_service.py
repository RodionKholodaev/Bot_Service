import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)


class ExchangeRateService:
    def __init__(self, retries: int = 3, delay: float = 1.5, timeout: int = 5):
        """
        Инициализация сервиса.
        :param retries: Количество попыток при сбое
        :param delay: Задержка между попытками (в секундах)
        :param timeout: Максимальное время ожидания ответа от сервера (в секундах)
        """
        self.url = "https://api.binance.com/api/v3/ticker/price?symbol=USDTRUB"
        self.retries = retries
        self.delay = delay
        self.timeout = httpx.Timeout(timeout)
        logger.info(
            "ExchangeRateService initialized",
            extra={"retries": retries, "delay": delay, "timeout": timeout},
        )

    async def get_usdt_rub(self) -> float | None:
        """
        Получает актуальный курс USDT/RUB.
        Возвращает float (курс) или None, если все попытки провалились.
        """
        logger.info("Fetching USDT/RUB rate from Binance")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(1, self.retries + 1):
                try:
                    response = await client.get(self.url)

                    response.raise_for_status()

                    data = response.json()

                    price = float(data.get("price", 0.0))

                    if price > 0:
                        logger.info(
                            "USDT/RUB rate fetched successfully",
                            extra={"price": price, "attempt": attempt},
                        )
                        return price
                    else:
                        logger.warning(
                            "Received zero or invalid price",
                            extra={"attempt": attempt, "raw_price": data.get("price")},
                        )

                except httpx.HTTPError as e:
                    logger.error(
                        "HTTP error while fetching rate",
                        extra={"attempt": attempt, "error": str(e)},
                    )
                except ValueError as e:
                    logger.error(
                        "Data parsing error",
                        extra={"attempt": attempt, "error": str(e)},
                    )
                except TimeoutError:
                    logger.error(
                        "Request timeout",
                        extra={"attempt": attempt, "timeout": self.timeout},
                    )

                if attempt < self.retries:
                    logger.info(
                        "Retrying after delay",
                        extra={"attempt": attempt, "delay": self.delay},
                    )
                    await asyncio.sleep(self.delay)

        logger.critical(
            "Failed to fetch USDT/RUB rate after all retries",
            extra={"total_attempts": self.retries},
        )
        return None
