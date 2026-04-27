# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
"""
MultiFilterStrategy — универсальная фьючерсная стратегия для Freqtrade.

Этот файл генерируется автоматически из шаблона.
Блок StrategyConfig подставляется бэкендом при создании бота.
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pandas import DataFrame
from typing import Optional, Union

from freqtrade.strategy import (
    IStrategy,
    Trade,
    Order,
    PairLocks,
    merge_informative_pair,
    stoploss_from_absolute,
    stoploss_from_open,
    timeframe_to_minutes,
)

import talib as ta  # type: ignore[reportMissingTypeStubs]

logger = logging.getLogger(__name__)


# ==============================================================================
#  НАСТРОЙКИ ПОЛЬЗОВАТЕЛЯ — генерируются бэкендом
# ==============================================================================

class StrategyConfig:
    BASE_TIMEFRAME = "1m"
    LEVERAGE = 5
    CAN_SHORT = False

    ENTRY_FILTERS_LONG = [{'indicator': 'rsi', 'timeframe': '1m', 'condition': 'less', 'value': 55}, {'indicator': 'cci', 'timeframe': '5m', 'condition': 'less', 'value': 0}]
    ENTRY_FILTERS_SHORT = []

    TAKE_PROFIT = {'0': 0.05}
    STOPLOSS = -0.02

    TRAILING_STOP = False
    TRAILING_STOP_POSITIVE = 0.001
    TRAILING_STOP_POSITIVE_OFFSET = 0.002
    TRAILING_ONLY_OFFSET_IS_REACHED = True


# ==============================================================================
#  СТРАТЕГИЯ
# ==============================================================================

class MultiFilterStrategy(IStrategy):
    INTERFACE_VERSION = 3

    can_short: bool = StrategyConfig.CAN_SHORT

    timeframe = StrategyConfig.BASE_TIMEFRAME
    stoploss = StrategyConfig.STOPLOSS
    trailing_stop = StrategyConfig.TRAILING_STOP
    trailing_stop_positive = StrategyConfig.TRAILING_STOP_POSITIVE
    trailing_stop_positive_offset = StrategyConfig.TRAILING_STOP_POSITIVE_OFFSET
    trailing_only_offset_is_reached = StrategyConfig.TRAILING_ONLY_OFFSET_IS_REACHED

    minimal_roi = {k: v for k, v in StrategyConfig.TAKE_PROFIT.items()}

    startup_candle_count: int = 200
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": True,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: Optional[str],
        side: str,
    ) -> float:
        return min(StrategyConfig.LEVERAGE, max_leverage)

    def _get_extra_timeframes(self):
        all_filters = StrategyConfig.ENTRY_FILTERS_LONG + StrategyConfig.ENTRY_FILTERS_SHORT
        tfs = set()
        for f in all_filters:
            if f["timeframe"] != StrategyConfig.BASE_TIMEFRAME:
                tfs.add(f["timeframe"])
        return list(tfs)

    def _col_name(self, indicator: str, timeframe: str) -> str:
        if timeframe == StrategyConfig.BASE_TIMEFRAME:
            return indicator
        return f"{indicator}_{timeframe}"

    def _apply_filters(self, dataframe: DataFrame, filters: list) -> pd.Series:
        conditions = []
        for f in filters:
            col = self._col_name(f["indicator"], f["timeframe"])
            if col not in dataframe.columns:
                logger.warning(f"Колонка '{col}' не найдена — фильтр пропущен.")
                continue
            if f["condition"] == "less":
                conditions.append(dataframe[col] < f["value"])
            elif f["condition"] == "greater":
                conditions.append(dataframe[col] > f["value"])
            elif f["condition"] == "less_equal":
                conditions.append(dataframe[col] <= f["value"])
            elif f["condition"] == "greater_equal":
                conditions.append(dataframe[col] >= f["value"])

        conditions.append(dataframe["volume"] > 0)

        if not conditions:
            return pd.Series(False, index=dataframe.index)

        combined = conditions[0]
        for c in conditions[1:]:
            combined = combined & c
        return combined

    def informative_pairs(self):
        pairs = self.dp.current_whitelist()
        result = []
        for tf in self._get_extra_timeframes():
            for pair in pairs:
                result.append((pair, tf))
        return result

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]

        dataframe["rsi"] = ta.RSI(dataframe["close"], timeperiod=14)
        dataframe["cci"] = ta.CCI(
            dataframe["high"], dataframe["low"], dataframe["close"], timeperiod=20
        )

        for tf in self._get_extra_timeframes():
            informative_df = self.dp.get_pair_dataframe(pair=pair, timeframe=tf)
            if informative_df is None or informative_df.empty:
                continue

            informative_df[f"rsi_{tf}"] = ta.RSI(informative_df["close"], timeperiod=14)
            informative_df[f"cci_{tf}"] = ta.CCI(
                informative_df["high"], informative_df["low"], informative_df["close"], timeperiod=20
            )

            dataframe = merge_informative_pair(
                dataframe,
                informative_df[["date", f"rsi_{tf}", f"cci_{tf}"]],
                self.timeframe,
                tf,
                ffill=True,
            )

            for ind in ["rsi", "cci"]:
                src_col = f"{ind}_{tf}_{tf}"
                dst_col = f"{ind}_{tf}"
                if src_col in dataframe.columns:
                    dataframe.rename(columns={src_col: dst_col}, inplace=True)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if StrategyConfig.ENTRY_FILTERS_LONG:
            long_signal = self._apply_filters(dataframe, StrategyConfig.ENTRY_FILTERS_LONG)
            dataframe.loc[long_signal, "enter_long"] = 1

        if StrategyConfig.CAN_SHORT and StrategyConfig.ENTRY_FILTERS_SHORT:
            short_signal = self._apply_filters(dataframe, StrategyConfig.ENTRY_FILTERS_SHORT)
            dataframe.loc[short_signal, "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, "exit_long"] = 0
        dataframe.loc[:, "exit_short"] = 0
        return dataframe
