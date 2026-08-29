export type BotDirection = 'long' | 'short';
export type StrategyPreset =
  'conservative' | 'moderate' | 'aggressive' | 'custom';
export type Indicator = 'rsi' | 'cci';
export type Timeframe = '1m' | '5m' | '15m' | '30m' | '1h' | '4h';
export type FilterCondition =
  'less' | 'greater' | 'less_equal' | 'greater_equal';

export interface FilterRule {
  indicator: Indicator;
  timeframe: Timeframe;
  condition: FilterCondition;
  value: number;
}

export interface BotCreatePayload {
  name: string;
  pair: string;
  leverage: number;
  direction: BotDirection;
  strategy_preset: StrategyPreset;
  entry_filters_long?: FilterRule[];
  entry_filters_short?: FilterRule[];
  take_profit_percent: number;
  stop_loss_enabled: boolean;
  stop_loss_percent?: number | null;
  dry_run: boolean;
  api_key_id: number | null;
  stake_amount: number;
  tradable_balance_ratio: number;
}

export interface BotPublic {
  id: string;
  name: string;
  pair: string;
  leverage: number;
  direction: string;
  strategy_preset: string;
  entry_filters_long: FilterRule[];
  entry_filters_short: FilterRule[];
  // Проценты движения цены, как их задал человек. null — у ботов, созданных до того,
  // как эти поля появились: тогда в базе есть только формат freqtrade (доли маржи).
  take_profit_percent: number | null;
  stop_loss_percent: number | null;
  // Имена достались от первой трактовки и не совпадают со смыслом (см. models/bot.py
  // на бэкенде): stake_amount — весь депозит бота, tradable_balance_ratio — доля
  // депозита на одну сделку (0.2 = 20%).
  stake_amount: number;
  tradable_balance_ratio: number;
  api_key_id: number | null;
  dry_run: boolean;
  status: string;
  error_message: string | null;
  api_port: number;
  created_at: string;
  total_profit?: number;
}

/** Готовый набор настроек стратегии — GET /bots/presets.
 *  Числа приходят с бэкенда: копии на фронте больше нет, иначе бот, созданный
 *  запросом с тем же именем пресета, отличался бы от нарисованного формой. */
export interface StrategyPresetOut {
  key: string;
  name: string;
  description: string;
  long_filters: FilterRule[];
  short_filters: FilterRule[];
  take_profit_percent: number;
  stop_loss_percent: number | null;
  stop_loss_enabled: boolean;
}
