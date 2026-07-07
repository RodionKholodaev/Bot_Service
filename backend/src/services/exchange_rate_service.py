import httpx
import asyncio
import logging

# Настраиваем базовое логирование для отслеживания проблем
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
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

    async def get_usdt_rub(self) -> float | None:
        """
        Получает актуальный курс USDT/RUB. 
        Возвращает float (курс) или None, если все попытки провалились.
        """
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(1, self.retries + 1):
                try:
                    response = await client.get(self.url)
                    
                    # Если статус ответа не 200 OK, вызываем исключение
                    response.raise_for_status()
                    
                    # httpx уже умеет парсить JSON
                    data = response.json()
                    
                    # Парсим цену (API отдает строку, поэтому переводим во float)
                    price = float(data.get("price", 0.0))
                    
                    if price > 0:
                        return price
                    else:
                        logger.warning(f"Попытка {attempt}: Получена нулевая или некорректная цена.")
                        
                except httpx.HTTPError as e:
                    # Общая ошибка HTTP (включает сетевые, статус-коды и т.д.)
                    logger.error(f"Попытка {attempt}: Ошибка HTTP - {e}")
                except ValueError as e:
                    # Ловим ошибки парсинга JSON или конвертации во float
                    logger.error(f"Попытка {attempt}: Ошибка обработки данных - {e}")
                except asyncio.TimeoutError:
                    # Ловим ситуации, когда сервер слишком долго не отвечает
                    logger.error(f"Попытка {attempt}: Превышено время ожидания ответа (Timeout).")
                
                # Если это не последняя попытка, ждем перед следующим запросом
                if attempt < self.retries:
                    await asyncio.sleep(self.delay)

        # Если цикл завершился и мы не вернули return price, значит всё сломалось
        logger.critical("Не удалось получить курс USDT/RUB после всех попыток.")
        return None