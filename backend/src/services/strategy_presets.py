"""
Пресеты стратегий — словарь "имя пресета → набор фильтров".

Значения подобраны на старте, ты их потом скорректируешь под свою торговую логику.
Логика простая:
  - Консервативная — редко входим, нужны очень понятные сигналы перепроданности/перекупленности
  - Умеренная — баланс между частотой и качеством
  - Агрессивная — заходим часто, на ранних сигналах
"""

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
    if preset == "custom":
        long_filters = list(custom_long or [])
        short_filters = list(custom_short or [])
    else:
        if preset not in PRESETS:
            raise ValueError(f"Unknown preset: {preset}")
        long_filters = list(PRESETS[preset]["long"])
        short_filters = list(PRESETS[preset]["short"])

    if direction == "long":
        short_filters = []
    elif direction == "short":
        long_filters = []

    return long_filters, short_filters
