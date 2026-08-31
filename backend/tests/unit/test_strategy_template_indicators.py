"""
Юнит-тесты набора индикаторов: схема, шаблон стратегии и валидатор ассистента
должны знать об одном и том же списке.

Проверять это тестом стоит потому, что расхождение не падает нигде. Индикатор,
который проходит FilterRule, но не считается в шаблоне, не приводит к ошибке:
_apply_filters в сгенерированной стратегии пишет warning в лог контейнера и
выбрасывает условие. Бот запустится и будет входить по более слабым условиям,
чем настроил пользователь, — молча.

Ни БД, ни сети: читаем сам файл шаблона и Literal из схемы.
"""

import ast
import re
from pathlib import Path
from typing import get_args

import pytest

from src.schemas.bot import FilterRule
from src.services.assistant.tools import _INDICATORS
from src.services.freqtrade_strategy import TEMPLATE_PATH

SCHEMA_INDICATORS = set(get_args(FilterRule.model_fields["indicator"].annotation))


def template_indicator_columns() -> set[str]:
    """Список INDICATOR_COLUMNS, как он записан в шаблоне стратегии."""
    template = Path(TEMPLATE_PATH).read_text(encoding="utf-8")
    match = re.search(r"^INDICATOR_COLUMNS = (\[.*?\])$", template, re.MULTILINE)
    assert match, "В шаблоне не найден список INDICATOR_COLUMNS"
    return set(ast.literal_eval(match.group(1)))


# ──────────────────────────────────────────────


def test_schema_and_template_know_the_same_indicators():
    """Состав индикаторов в схеме и в шаблоне совпадает — в обе стороны."""
    # Arrange / Act
    template_columns = template_indicator_columns()

    # Assert
    assert template_columns == SCHEMA_INDICATORS


@pytest.mark.parametrize("indicator", sorted(SCHEMA_INDICATORS))
def test_every_indicator_is_computed_in_template(indicator):
    """Для каждого индикатора схемы в шаблоне есть присвоение колонки.

    Одного INDICATOR_COLUMNS мало: список может перечислять колонку, которую
    compute_indicators не заполняет, — тогда фильтр так же тихо выпадет.
    """
    # Arrange
    template = Path(TEMPLATE_PATH).read_text(encoding="utf-8")

    # Act / Assert — df[f"rsi{suffix}"] = ...
    assert f'df[f"{indicator}{{suffix}}"] =' in template


def test_assistant_offers_the_same_indicators_as_the_schema():
    """Ассистент не предлагает того, что не примет схема — и наоборот."""
    assert _INDICATORS == SCHEMA_INDICATORS


@pytest.mark.parametrize("indicator", sorted(SCHEMA_INDICATORS))
def test_filter_rule_accepts_every_supported_indicator(indicator):
    rule = FilterRule(indicator=indicator, timeframe="5m", condition="less", value=30)
    assert rule.indicator == indicator


def test_filter_rule_rejects_unknown_indicator():
    with pytest.raises(ValueError):
        FilterRule(indicator="macd", timeframe="5m", condition="less", value=30)
