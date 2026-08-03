"""
Пресеты стратегий — словарь "имя пресета → набор фильтров".

Значения подобраны на старте, ты их потом скорректируешь под свою торговую логику.
Логика простая:
  - Консервативная — редко входим, нужны очень понятные сигналы перепроданности/перекупленности
  - Умеренная — баланс между частотой и качеством
  - Агрессивная — заходим часто, на ранних сигналах
"""

import logging

logger = logging.getLogger(__name__)

PRESETS: dict[str, dict[str, list[dict]]] = {
    "conservative": {
        "long": [
            {"indicator": "rsi", "timeframe": "5m",  "condition": "less", "value": 30},
            {"indicator": "rsi", "timeframe": "15m", "condition": "less", "value": 35},
            {"indicator": "cci", "timeframe": "1h",  "condition": "less", "value": -100},
        ],
        "short": [
            {"indicator": "rsi", "timeframe": "5m",  "condition": "greater", "value": 70},
            {"indicator": "rsi", "timeframe": "15m", "condition": "greater", "value": 65},
            {"indicator": "cci", "timeframe": "1h",  "condition": "greater", "value": 100},
        ],
    },
    "moderate": {
        "long": [
            {"indicator": "rsi", "timeframe": "1m",  "condition": "less", "value": 40},
            {"indicator": "rsi", "timeframe": "5m",  "condition": "less", "value": 45},
            {"indicator": "cci", "timeframe": "30m", "condition": "less", "value": -50},
        ],
        "short": [
            {"indicator": "rsi", "timeframe": "1m",  "condition": "greater", "value": 60},
            {"indicator": "rsi", "timeframe": "5m",  "condition": "greater", "value": 55},
            {"indicator": "cci", "timeframe": "30m", "condition": "greater", "value": 50},
        ],
    },
    "aggressive": {
        "long": [
            {"indicator": "rsi", "timeframe": "1m", "condition": "less", "value": 55},
            {"indicator": "cci", "timeframe": "5m", "condition": "less", "value": 0},
        ],
        "short": [
            {"indicator": "rsi", "timeframe": "1m", "condition": "greater", "value": 55},
            {"indicator": "cci", "timeframe": "5m", "condition": "greater", "value": 0},
        ],
    },
}


def resolve_filters(
    preset: str,
    direction: str,
    custom_long: list[dict] | None = None,
    custom_short: list[dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Возвращает (long_filters, short_filters) для бота.

    Если direction=="long" — short_filters пустой и наоборот.
    Для preset="custom" — берёт custom_long/custom_short, для остальных — из PRESETS.
    """
    logger.debug(
        "Resolving strategy filters",
        extra={
            "preset": preset,
            "direction": direction,
            "has_custom_long": custom_long is not None,
            "has_custom_short": custom_short is not None,
        },
    )

    if preset == "custom":
        long_filters = list(custom_long or [])
        short_filters = list(custom_short or [])
        logger.debug(
            "Using custom filters",
            extra={"long_count": len(long_filters), "short_count": len(short_filters)},
        )
    else:
        if preset not in PRESETS:
            logger.error(
                "Unknown preset requested",
                extra={"preset": preset, "available": list(PRESETS.keys())},
            )
            raise ValueError(f"Unknown preset: {preset}")
        long_filters = list(PRESETS[preset]["long"])
        short_filters = list(PRESETS[preset]["short"])
        logger.debug(
            "Preset filters loaded",
            extra={
                "preset": preset,
                "long_count": len(long_filters),
                "short_count": len(short_filters),
            },
        )

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