"""
Юнит-тесты для валидации предложений ИИ-ассистента.

Модель — источник недоверенных данных: она вполне может предложить плечо x300,
индикатор, которого в продукте нет, или строку вместо числа. Всё это уезжает
прямо в форму создания бота, поэтому normalize_suggestions обязан пропускать
только то, что форма реально умеет принять, а остальное молча выбрасывать.

Тесты без сети и без БД: normalize_suggestions — чистая функция от JSON-строки.
"""

import json

import pytest

from src.services.assistant.tools import SUGGESTABLE_FIELDS, normalize_suggestions


def _args(*suggestions: dict) -> str:
    """Аргументы вызова suggest_settings в том виде, в каком их шлёт модель."""
    return json.dumps({"suggestions": list(suggestions)})


# По одному заведомо валидному значению на каждое поле из SUGGESTABLE_FIELDS.
# Используется в test_every_advertised_field_survives_normalization — см. комментарий там.
VALID_VALUE_PER_FIELD: dict[str, object] = {
    "dryRun": True,
    "stakeAmount": 100,
    "balanceRatio": 20,
    "tradingPair": "BTC/USDT",
    "leverage": 3,
    "algorithm": "long",
    "strategyPreset": "moderate",
    "filters": [{"indicator": "rsi", "timeframe": "5m", "condition": "less", "value": 30}],
    "botName": "Мой бот",
    "takeProfit": 2.5,
    "useStopLoss": True,
    "stopLoss": 1.5,
}


def test_valid_suggestions_pass_through_as_form_values():
    # Arrange — числа модель шлёт числами, а форма хранит их строками
    raw = _args(
        {"field": "leverage", "value": 3, "reason": "новичку хватит"},
        {"field": "takeProfit", "value": 2.5, "reason": "реалистичная цель"},
    )

    # Act
    result = normalize_suggestions(raw)

    # Assert
    assert result == [
        {"field": "leverage", "value": "3", "reason": "новичку хватит"},
        {"field": "takeProfit", "value": "2.5", "reason": "реалистичная цель"},
    ]


def test_out_of_range_values_are_dropped():
    # Arrange — плечо в форме ограничено x20, депозит должен быть положительным
    raw = _args(
        {"field": "leverage", "value": 300, "reason": "рискнём"},
        {"field": "stakeAmount", "value": -50, "reason": "минус"},
        {"field": "takeProfit", "value": 3, "reason": "ок"},
    )

    # Act
    result = normalize_suggestions(raw)

    # Assert — остаётся только валидное
    assert [item["field"] for item in result] == ["takeProfit"]


def test_balance_ratio_snaps_to_slider_step():
    # Arrange — ползунок «размер сделки» ходит с шагом 5
    raw = _args({"field": "balanceRatio", "value": 13, "reason": "поменьше"})

    # Act
    result = normalize_suggestions(raw)

    # Assert
    assert result[0]["value"] == "15"


def test_unknown_field_is_ignored():
    # Arrange — поля stopLossTrailing в продукте нет
    raw = _args(
        {"field": "stopLossTrailing", "value": True, "reason": "выдумка"},
        {"field": "botName", "value": "BTC скальпер", "reason": "понятное имя"},
    )

    # Act
    result = normalize_suggestions(raw)

    # Assert
    assert [item["field"] for item in result] == ["botName"]


def test_every_advertised_field_survives_normalization():
    # Arrange
    # SUGGESTABLE_FIELDS уезжает в enum схемы инструмента — модель считает, что все
    # эти поля можно предлагать. Но пропускает значения _normalize_value, у которого
    # свой список веток и свой финальный `return None`.
    #
    # Оба списка нужно править вместе. Если добавить поле только в SUGGESTABLE_FIELDS,
    # модель начнёт его предлагать, а нормализатор — молча выбрасывать: ассистент
    # «советует», карточка не появляется, и по логам это выглядит как каприз модели.
    # Тест ловит именно такую рассинхронизацию.
    assert VALID_VALUE_PER_FIELD.keys() == SUGGESTABLE_FIELDS.keys(), (
        "Список полей в тесте разошёлся с SUGGESTABLE_FIELDS — "
        "добавьте валидное значение для нового поля в VALID_VALUE_PER_FIELD"
    )

    for field, value in VALID_VALUE_PER_FIELD.items():
        # Act
        result = normalize_suggestions(_args({"field": field, "value": value, "reason": "ок"}))

        # Assert
        assert len(result) == 1, f"поле {field} объявлено ассистенту, но отбраковано нормализатором"
        assert result[0]["field"] == field


@pytest.mark.parametrize(
    "field, value",
    [
        ("dryRun", "не булево"),
        ("stakeAmount", "не число"),
        ("balanceRatio", 3),            # ниже минимума ползунка (5)
        ("tradingPair", "BTCUSDT"),     # без слэша
        ("leverage", 0),                # ниже минимума формы (1)
        ("algorithm", "sideways"),      # направления нет в продукте
        ("strategyPreset", "scalping"), # пресета нет в продукте
        ("filters", "не массив"),
        ("botName", "   "),             # пустое после strip
        ("takeProfit", 0),              # ноль процентов — не цель
        ("useStopLoss", 1),             # число вместо булева
        ("stopLoss", 150),              # больше 100%
    ],
)
def test_invalid_value_is_dropped_for_each_field(field, value):
    # Arrange — на каждое поле по одному характерному «мусорному» значению
    raw = _args({"field": field, "value": value, "reason": "мимо"})

    # Act
    result = normalize_suggestions(raw)

    # Assert
    assert result == []


def test_no_more_than_eight_suggestions_are_returned():
    # Arrange
    # В схеме инструмента стоит maxItems: 8, но схема — это просьба к модели, а не
    # гарантия. Форма рисует карточку на каждое предложение, поэтому лимит
    # дублируется на нашей стороне.
    raw = _args(*[
        {"field": field, "value": value, "reason": "ок"}
        for field, value in VALID_VALUE_PER_FIELD.items()
    ])

    # Act
    result = normalize_suggestions(raw)

    # Assert: полей 12, но наружу уходит только 8 первых
    assert len(VALID_VALUE_PER_FIELD) > 8
    assert len(result) == 8
    assert [item["field"] for item in result] == list(VALID_VALUE_PER_FIELD)[:8]


def test_filters_keep_only_supported_indicators_and_timeframes():
    # Arrange — в продукте есть только rsi/cci и фиксированный набор таймфреймов
    raw = _args(
        {
            "field": "filters",
            "value": [
                {"indicator": "rsi", "timeframe": "5m", "condition": "less", "value": 30},
                {"indicator": "macd", "timeframe": "5m", "condition": "less", "value": 0},
                {"indicator": "cci", "timeframe": "2h", "condition": "less", "value": -100},
                {"indicator": "cci", "timeframe": "1h", "condition": "less", "value": -100},
            ],
            "reason": "вход на перепроданности",
        }
    )

    # Act
    result = normalize_suggestions(raw)

    # Assert — macd и таймфрейм 2h выброшены, остальное сохранено
    assert result[0]["value"] == [
        {"indicator": "rsi", "timeframe": "5m", "condition": "less", "value": 30.0},
        {"indicator": "cci", "timeframe": "1h", "condition": "less", "value": -100.0},
    ]


def test_filters_are_dropped_entirely_when_nothing_survives():
    # Arrange — пустой список фильтров в форме означал бы бота, который никогда не входит
    raw = _args(
        {
            "field": "filters",
            "value": [{"indicator": "macd", "timeframe": "5m", "condition": "less", "value": 0}],
            "reason": "всё мимо",
        }
    )

    # Act
    result = normalize_suggestions(raw)

    # Assert
    assert result == []


def test_duplicate_field_keeps_first_occurrence():
    # Arrange — применять два разных значения одного поля бессмысленно
    raw = _args(
        {"field": "leverage", "value": 2, "reason": "первое"},
        {"field": "leverage", "value": 5, "reason": "второе"},
    )

    # Act
    result = normalize_suggestions(raw)

    # Assert
    assert result == [{"field": "leverage", "value": "2", "reason": "первое"}]


def test_malformed_arguments_do_not_raise():
    # Arrange — модель иногда обрывает JSON на полуслове
    # Act / Assert — вместо исключения просто пустой список
    assert normalize_suggestions('{"suggestions": [{"field": "lever') == []
    assert normalize_suggestions("") == []
    assert normalize_suggestions('{"suggestions": "не массив"}') == []
