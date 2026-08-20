"""
Генерация файла стратегии MultiFilterStrategy.py для каждого бота из шаблона.

Подставляет в плейсхолдеры (в блоке StrategyConfig) значения пользователя.
Используем repr() для сериализации Python-литералов (списков/словарей/булевых) —
он гарантированно даёт валидный Python-синтаксис.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "multifilter_strategy.template"

TF_ORDER = ["1m", "5m", "15m", "30m", "1h", "4h"]


def _get_base_timeframe(filters_long: list[dict], filters_short: list[dict]) -> str:
    all_tfs = [f["timeframe"] for f in filters_long + filters_short]
    if not all_tfs:
        logger.warning(
            "No timeframes found in filters, falling back to 5m",
            extra={
                "filters_long_count": len(filters_long),
                "filters_short_count": len(filters_short),
            },
        )
        return "5m"
    base_tf = min(all_tfs, key=lambda tf: TF_ORDER.index(tf) if tf in TF_ORDER else 99)
    logger.debug(
        "Base timeframe resolved",
        extra={"base_timeframe": base_tf, "available_timeframes": all_tfs},
    )
    return base_tf


def generate_strategy_file(
    leverage: int,
    can_short: bool,
    entry_filters_long: list[dict],
    entry_filters_short: list[dict],
    take_profit: dict,
    stoploss: float,
    trailing_stop: bool,
) -> str:
    """Возвращает содержимое .py файла стратегии как строку."""
    logger.info(
        "Generating strategy file",
        extra={
            "leverage": leverage,
            "can_short": can_short,
            "long_filters_count": len(entry_filters_long),
            "short_filters_count": len(entry_filters_short),
            "stoploss": stoploss,
            "trailing_stop": trailing_stop,
        },
    )

    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        template = f.read()

    # take_profit ключи приходят как строки ("0", "30") — это требование freqtrade
    # для minimal_roi. Сохраняем формат.
    tp_dict = {str(k): float(v) for k, v in take_profit.items()}

    base_tf = _get_base_timeframe(entry_filters_long, entry_filters_short)

    replacements = {
        "{{BASE_TIMEFRAME}}": repr(base_tf),
        "{{LEVERAGE}}": repr(int(leverage)),
        "{{CAN_SHORT}}": repr(bool(can_short)),
        "{{ENTRY_FILTERS_LONG}}": repr(entry_filters_long),
        "{{ENTRY_FILTERS_SHORT}}": repr(entry_filters_short),
        "{{TAKE_PROFIT}}": repr(tp_dict),
        "{{STOPLOSS}}": repr(float(stoploss)),
        "{{TRAILING_STOP}}": repr(bool(trailing_stop)),
    }

    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)

    logger.info(
        "Strategy file generated successfully",
        extra={"base_timeframe": base_tf, "replacements_count": len(replacements)},
    )
    return rendered


def write_strategy_file(content: str, target_path: Path) -> None:
    logger.info(
        "Writing strategy file to disk",
        extra={"target_path": str(target_path)},
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info(
        "Strategy file written successfully",
        extra={"target_path": str(target_path)},
    )
