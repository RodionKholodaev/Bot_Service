"""
Юнит-тесты пресетов стратегий: кто побеждает — присланное или пресет.

До этих тестов PRESETS не вызывался вообще никогда: фронт держал свою копию наборов
(с другими числами) и всегда слал strategy_preset="custom". Поэтому проверять надо две
вещи сразу — что пресет раскрывается, когда его просят, и что он НЕ переписывает то,
что человек поправил руками в форме. Интерфейс шлёт и имя пресета, и фильтры с
процентами; на экране видны вторые, и в базу должны попасть тоже они.

Ни БД, ни сети: resolve_filters — чистая функция, BotCreate — pydantic-схема.
"""

import pytest
from pydantic import ValidationError

from src.schemas.bot import BotCreate, StrategyPresetOut
from src.services.strategy_presets import PRESETS, list_presets, resolve_filters

CUSTOM_LONG = [{"indicator": "rsi", "timeframe": "1m", "condition": "less", "value": 20}]
CUSTOM_SHORT = [{"indicator": "cci", "timeframe": "4h", "condition": "greater", "value": 200}]


def make_body(**overrides) -> BotCreate:
    """Валидное тело POST /bots. По умолчанию — пресет и ни одного поля стратегии."""
    data = {
        "name": "bot",
        "pair": "XRP/USDT:USDT",
        "leverage": 10,
        "direction": "long",
        "strategy_preset": "moderate",
        "dry_run": True,
        "api_key_id": None,
        "stake_amount": 100.0,
        "tradable_balance_ratio": 0.5,
    }
    data.update(overrides)
    return BotCreate(**data)


# ──────────────────────────────────────────────
# resolve_filters: присланное сильнее пресета
# ──────────────────────────────────────────────


def test_sent_filters_win_over_preset_name():
    # Arrange / Act
    # имя пресета не custom, но фильтры присланы — значит человек их правил в форме
    long_filters, _ = resolve_filters("moderate", "long", custom_long=CUSTOM_LONG)

    # Assert
    assert long_filters == CUSTOM_LONG
    # старое поведение молча подставляло бы сюда три условия «умеренного»
    assert long_filters != PRESETS["moderate"]["long_filters"]


def test_preset_expands_when_no_filters_sent():
    # Arrange / Act
    long_filters, _ = resolve_filters("moderate", "long")

    # Assert
    assert long_filters == PRESETS["moderate"]["long_filters"]


def test_sent_short_filters_win_over_preset_name():
    # Arrange / Act
    long_filters, short_filters = resolve_filters("moderate", "short", custom_short=CUSTOM_SHORT)

    # Assert
    assert short_filters == CUSTOM_SHORT
    # направление одно, поэтому противоположная сторона всегда пустая
    assert long_filters == []


def test_custom_preset_without_filters_gives_empty_lists():
    # Arrange / Act
    long_filters, short_filters = resolve_filters("custom", "long")

    # Assert
    # custom раскрывать нечем — схема такое тело и не пропустит, но функция не падает
    assert long_filters == []
    assert short_filters == []


def test_direction_clears_the_opposite_side_of_a_preset():
    # Arrange / Act
    long_only, short_of_long = resolve_filters("aggressive", "long")
    long_of_short, short_only = resolve_filters("aggressive", "short")

    # Assert
    assert short_of_long == []
    assert long_of_short == []
    assert long_only == PRESETS["aggressive"]["long_filters"]
    assert short_only == PRESETS["aggressive"]["short_filters"]


def test_unknown_preset_is_rejected():
    # Arrange / Act / Assert
    with pytest.raises(ValueError, match="Unknown preset"):
        resolve_filters("legendary", "long")


# ──────────────────────────────────────────────
# list_presets: то, что уезжает в форму
# ──────────────────────────────────────────────


def test_every_preset_is_serializable_for_the_form():
    # Arrange / Act
    payload = list_presets()

    # Assert
    assert {p["key"] for p in payload} == set(PRESETS)
    # схема ответа строгая: не хватит поля или разъедется тип фильтра — упадёт здесь,
    # а не молчаливой пустой карточкой в форме
    for item in payload:
        StrategyPresetOut.model_validate(item)


# ──────────────────────────────────────────────
# BotCreate: пресет подставляет TP/SL
# ──────────────────────────────────────────────


def test_preset_fills_take_profit_and_stop_loss_when_body_omits_them():
    # Arrange / Act
    body = make_body(strategy_preset="moderate")

    # Assert
    # запрос мимо интерфейса с одним лишь именем пресета должен дать того же бота,
    # которого рисует форма
    assert body.take_profit_percent == PRESETS["moderate"]["take_profit_percent"]
    assert body.stop_loss_percent == PRESETS["moderate"]["stop_loss_percent"]
    assert body.stop_loss_enabled is True


def test_sent_percents_win_over_preset():
    # Arrange / Act
    body = make_body(strategy_preset="moderate", take_profit_percent=7.0, stop_loss_percent=3.0)

    # Assert
    assert body.take_profit_percent == 7.0
    assert body.stop_loss_percent == 3.0


def test_explicitly_disabled_stop_loss_is_not_restored_by_the_preset():
    # Arrange / Act
    body = make_body(strategy_preset="moderate", stop_loss_enabled=False)

    # Assert
    # «умеренный» несёт стоп 1.5%, но человек снял галочку — пресет не должен её вернуть
    assert body.stop_loss_enabled is False
    assert body.stop_loss_percent is None


def test_preset_filters_are_optional_in_the_body():
    # Arrange / Act
    body = make_body(strategy_preset="conservative")

    # Assert
    # фильтры раскроет resolve_filters; требовать их в теле — значит требовать от
    # клиента знать наборы, которые и так лежат на бэкенде
    assert body.entry_filters_long is None


def test_custom_strategy_still_requires_filters_and_take_profit():
    # Arrange / Act / Assert
    with pytest.raises(ValidationError, match="entry_filters_long"):
        make_body(strategy_preset="custom", take_profit_percent=1.5)

    with pytest.raises(ValidationError, match="take_profit_percent"):
        make_body(
            strategy_preset="custom",
            entry_filters_long=CUSTOM_LONG,
        )


def test_leverage_limit_is_checked_against_the_substituted_preset_value():
    # Arrange / Act / Assert
    # «агрессивный» несёт стоп 2%: при x50 это вся маржа и позиции уже нет. Проверка
    # обязана видеть подставленное значение — иначе бот создастся, а контейнер упадёт
    with pytest.raises(ValidationError, match="съедает всю маржу"):
        make_body(strategy_preset="aggressive", leverage=50)

    # при x10 тот же пресет проходит: 2% * 10 = 20% маржи
    assert make_body(strategy_preset="aggressive", leverage=10).stop_loss_percent == 2.0
