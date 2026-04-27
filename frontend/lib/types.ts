export type BotDirection = "long" | "short" | "both";
export type StrategyPreset = "conservative" | "moderate" | "aggressive" | "custom";
export type Indicator = "rsi" | "cci";
export type Timeframe = "1m" | "5m" | "15m" | "30m" | "1h" | "4h";
export type FilterCondition = "less" | "greater" | "less_equal" | "greater_equal";

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
  api_key_id: string;
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
  take_profit: Record<string, number>;
  stop_loss: number;
  dry_run: boolean;
  status: string;
  error_message: string | null;
  api_port: number;
  created_at: string;
}