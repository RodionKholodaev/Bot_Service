"""
Генерация файла стратегии MultiFilterStrategy.py для каждого бота из шаблона.

Подставляет в плейсхолдеры (в блоке StrategyConfig) значения пользователя.
Используем repr() для сериализации Python-литералов (списков/словарей/булевых) —
он гарантированно даёт валидный Python-синтаксис.
"""

from pathlib import Path

TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent / "templates" / "multifilter_strategy.template.py"
)


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
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    # take_profit ключи приходят как строки ("0", "30") — это требование freqtrade
    # для minimal_roi. Сохраняем формат.
    tp_dict = {str(k): float(v) for k, v in take_profit.items()}

    replacements = {
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

    return rendered


def write_strategy_file(content: str, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(content)
