import type { FilterRule } from '@/lib/types';
import { PRESET_LABELS, indicatorLabel } from '@/lib/constants';
import type { Suggestion, SuggestableField } from './types';

/** Как показать предложение ассистента человеку: подпись поля, шаг мастера,
 *  и читаемое значение. Добавили поле в форму — добавьте строку сюда. */

interface FieldMeta {
  label: string;
  /** Шаг мастера, на котором живёт поле — по нему кнопка «Применить» перекидывает пользователя. */
  step: number;
  format: (value: Suggestion['value']) => string;
}

export function formatFilterRule(rule: FilterRule): string {
  const sign =
    rule.condition === 'less' || rule.condition === 'less_equal' ? '<' : '>';
  return `${indicatorLabel(rule.indicator)} ${rule.timeframe} ${sign} ${rule.value}`;
}

export const FIELD_META: Record<SuggestableField, FieldMeta> = {
  dryRun: {
    label: 'Режим торговли',
    step: 1,
    format: (v) => (v ? '🧪 Dry Run' : '🔴 Боевой'),
  },
  stakeAmount: { label: 'Депозит бота', step: 1, format: (v) => `${v} USDT` },
  balanceRatio: {
    label: 'Размер сделки',
    step: 1,
    format: (v) => `${v}% от депозита`,
  },
  tradingPair: { label: 'Торговая пара', step: 2, format: (v) => String(v) },
  leverage: { label: 'Плечо', step: 2, format: (v) => `x${v}` },
  algorithm: {
    label: 'Направление',
    step: 2,
    format: (v) => (v === 'long' ? '📈 Лонг' : '📉 Шорт'),
  },
  strategyPreset: {
    label: 'Стратегия',
    step: 3,
    format: (v) => PRESET_LABELS[String(v)] ?? String(v),
  },
  filters: {
    label: 'Условия входа',
    step: 3,
    format: (v) => (Array.isArray(v) ? `${v.length} усл.` : '—'),
  },
  botName: { label: 'Имя бота', step: 4, format: (v) => String(v) },
  takeProfit: { label: 'Take Profit', step: 4, format: (v) => `${v}%` },
  useStopLoss: {
    label: 'Stop Loss',
    step: 4,
    format: (v) => (v ? 'Включить' : 'Выключить'),
  },
  stopLoss: { label: 'Stop Loss', step: 4, format: (v) => `${v}%` },
};

/** Наименьший шаг из набора предложений — туда и ведём пользователя после «Применить». */
export function firstStepOf(suggestions: Suggestion[]): number {
  return suggestions.reduce(
    (min, s) => Math.min(min, FIELD_META[s.field]?.step ?? 4),
    4,
  );
}
