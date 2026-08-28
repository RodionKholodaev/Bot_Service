"""
Пресеты стратегий — единственный источник готовых наборов настроек.

Раньше наборов было два: этот словарь и его копия в форме создания бота на фронте,
с другими числами. Фронт всегда слал ``strategy_preset="custom"`` вместе со своими
фильтрами, поэтому словарь здесь не вызывался никогда, а запрос в POST /bots мимо
интерфейса создавал не того бота, которого интерфейс показывает. Теперь значения
живут здесь, фронт забирает их через GET /bots/presets и своих чисел не хранит.

Пресет задаёт не только условия входа, но и TP/SL — в интерфейсе выбор пресета
заполняет и их тоже.

Характер наборов:
  - Консервативный — много мелких сделок, небольшая цель, быстрый выход из убытка
  - Умеренный — баланс частоты и размера цели
  - Агрессивный — ставка на крупное движение, входит редко

Проценты TP/SL — движение ЦЕНЫ, как их вводит человек; в доли маржи их переводит
плечо уже в BotService._build_take_profit/_build_stoploss.
"""

import logging

logger = logging.getLogger(__name__)

PRESETS: dict[str, dict] = {
    "conservative": {
        "name": "Консервативный",
        "description": "Минимальный риск, небольшая прибыль",
        "long_filters": [
            {"indicator": "rsi", "timeframe": "1m", "condition": "less", "value": 50},
            {"indicator": "rsi", "timeframe": "5m", "condition": "less", "value": 50},
            {"indicator": "rsi", "timeframe": "30m", "condition": "less", "value": 50},
            {"indicator": "rsi", "timeframe": "1h", "condition": "less", "value": 55},
            {"indicator": "cci", "timeframe": "5m", "condition": "less", "value": 70},
            {"indicator": "cci", "timeframe": "15m", "condition": "less", "value": 75},
            {"indicator": "cci", "timeframe": "1h", "condition": "less", "value": 80},
        ],
        "short_filters": [
            {"indicator": "rsi", "timeframe": "1m", "condition": "greater", "value": 50},
            {"indicator": "rsi", "timeframe": "5m", "condition": "greater", "value": 50},
            {"indicator": "rsi", "timeframe": "30m", "condition": "greater", "value": 50},
            {"indicator": "rsi", "timeframe": "1h", "condition": "greater", "value": 55},
            {"indicator": "cci", "timeframe": "5m", "condition": "greater", "value": 70},
            {"indicator": "cci", "timeframe": "15m", "condition": "greater", "value": 75},
            {"indicator": "cci", "timeframe": "1h", "condition": "greater", "value": 80},
        ],
        "take_profit_percent": 1.5,
        "stop_loss_percent": 1.0,
        "stop_loss_enabled": True,
    },
    "moderate": {
        "name": "Умеренный",
        "description": "Баланс риска и прибыли",
        "long_filters": [
            {"indicator": "rsi", "timeframe": "5m", "condition": "less", "value": 55},
            {"indicator": "rsi", "timeframe": "30m", "condition": "less", "value": 65},
            {"indicator": "cci", "timeframe": "1h", "condition": "less", "value": 85},
        ],
        "short_filters": [
            {"indicator": "rsi", "timeframe": "5m", "condition": "greater", "value": 55},
            {"indicator": "rsi", "timeframe": "30m", "condition": "greater", "value": 65},
            {"indicator": "cci", "timeframe": "1h", "condition": "greater", "value": 85},
        ],
        "take_profit_percent": 2.5,
        "stop_loss_percent": 1.5,
        "stop_loss_enabled": True,
    },
    "aggressive": {
        "name": "Агрессивный",
        "description": "Высокий риск, максимальная прибыль",
        "long_filters": [
            {"indicator": "rsi", "timeframe": "1m", "condition": "less", "value": 35},
            {"indicator": "rsi", "timeframe": "5m", "condition": "less", "value": 35},
            {"indicator": "rsi", "timeframe": "30m", "condition": "less", "value": 35},
            {"indicator": "rsi", "timeframe": "4h", "condition": "less", "value": 35},
        ],
        "short_filters": [
            {"indicator": "rsi", "timeframe": "1m", "condition": "greater", "value": 35},
            {"indicator": "rsi", "timeframe": "5m", "condition": "greater", "value": 35},
            {"indicator": "rsi", "timeframe": "30m", "condition": "greater", "value": 35},
            {"indicator": "rsi", "timeframe": "4h", "condition": "greater", "value": 35},
        ],
        "take_profit_percent": 5.0,
        "stop_loss_percent": 2.0,
        "stop_loss_enabled": True,
    },
}


def get_preset(preset: str) -> dict | None:
    """Набор по имени. None — если это "custom" или имя неизвестно."""
    return PRESETS.get(preset)


def list_presets() -> list[dict]:
    """Все пресеты для GET /bots/presets: тот же словарь плюс ключ в поле key."""
    return [{"key": key, **data} for key, data in PRESETS.items()]


def resolve_filters(
    preset: str,
    direction: str,
    custom_long: list[dict] | None = None,
    custom_short: list[dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Возвращает (long_filters, short_filters) для бота.

    Присланные фильтры сильнее пресета — при любом его имени. Иначе имя пресета
    в теле запроса молча переписывало бы условия, которые человек поправил руками
    в форме: интерфейс шлёт и имя, и фильтры, и на экране видны вторые. Пресет
    раскрывается только там, где фильтров не прислали вовсе.

    Если direction=="long" — short_filters пустой и наоборот.
    """
    logger.debug(
        "Resolving strategy filters",
        extra={
            "preset": preset,
            "direction": direction,
            "has_custom_long": bool(custom_long),
            "has_custom_short": bool(custom_short),
        },
    )

    preset_data = None
    if preset != "custom":
        preset_data = get_preset(preset)
        if preset_data is None:
            logger.error(
                "Unknown preset requested",
                extra={"preset": preset, "available": list(PRESETS.keys())},
            )
            raise ValueError(f"Unknown preset: {preset}")

    def pick(custom: list[dict] | None, preset_key: str) -> list[dict]:
        if custom:
            return list(custom)
        if preset_data is not None:
            return list(preset_data[preset_key])
        return []

    long_filters = pick(custom_long, "long_filters")
    short_filters = pick(custom_short, "short_filters")

    if direction == "long":
        short_filters = []
        logger.debug("Direction is long, short filters cleared")
    elif direction == "short":
        long_filters = []
        logger.debug("Direction is short, long filters cleared")

    logger.debug(
        "Filters resolved",
        extra={"final_long_count": len(long_filters), "final_short_count": len(short_filters)},
    )
    return long_filters, short_filters
