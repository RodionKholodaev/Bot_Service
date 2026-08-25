import type { FilterRule } from '@/lib/types';
import type { BotFormSnapshot, Suggestion } from './types';

/** Состояние мастера создания бота. Живёт здесь, а не в page.tsx,
 *  чтобы и форма, и ассистент ссылались на один и тот же тип. */
export interface BotFormValues {
  selectedApiKeyId: string;
  exchange: string;
  stakeAmount: string;
  balanceRatio: string;
  tradingPair: string;
  leverage: string;
  algorithm: string;
  strategyPreset: string;
  filters: FilterRule[];
  botName: string;
  takeProfit: string;
  stopLoss: string;
  useStopLoss: boolean;
  dryRun: boolean;
}

/** Ключ биржи для подстановки при переключении в боевой режим. */
interface ApiKeyOption {
  id: string;
  exchange: string;
}

/** Применяет предложения ассистента к форме.
 *
 *  Кроме самого значения тянет за собой связанные поля, иначе форма
 *  окажется в противоречивом состоянии:
 *  - filters имеют смысл только при strategyPreset === 'custom'
 *    (иначе useEffect в page.tsx перезапишет их значениями пресета);
 *  - stopLoss без галочки useStopLoss просто не уедет на бэкенд;
 *  - боевой режим требует выбранного API-ключа. */
export function applySuggestionsToForm(
  form: BotFormValues,
  suggestions: Suggestion[],
  firstApiKey?: ApiKeyOption,
): BotFormValues {
  let next: BotFormValues = { ...form };

  for (const suggestion of suggestions) {
    switch (suggestion.field) {
      case 'filters':
        next = {
          ...next,
          filters: suggestion.value as FilterRule[],
          strategyPreset: 'custom',
        };
        break;

      case 'stopLoss':
        next = {
          ...next,
          stopLoss: String(suggestion.value),
          useStopLoss: true,
        };
        break;

      case 'useStopLoss':
        next = { ...next, useStopLoss: Boolean(suggestion.value) };
        break;

      case 'dryRun': {
        const dryRun = Boolean(suggestion.value);
        next = {
          ...next,
          dryRun,
          selectedApiKeyId: dryRun ? '' : (firstApiKey?.id ?? ''),
          exchange: dryRun
            ? 'binance'
            : (firstApiKey?.exchange ?? next.exchange),
        };
        break;
      }

      case 'strategyPreset':
        next = { ...next, strategyPreset: String(suggestion.value) };
        break;

      default:
        next = { ...next, [suggestion.field]: String(suggestion.value) };
        break;
    }
  }

  return next;
}

/** Снимок формы для ассистента: только то, что ему нужно видеть. */
export function toSnapshot(
  form: BotFormValues,
  step: number,
  hasApiKeys: boolean,
): BotFormSnapshot {
  return {
    step,
    hasApiKeys,
    dryRun: form.dryRun,
    stakeAmount: form.stakeAmount,
    balanceRatio: form.balanceRatio,
    tradingPair: form.tradingPair,
    leverage: form.leverage,
    algorithm: form.algorithm,
    strategyPreset: form.strategyPreset,
    filters: form.filters,
    botName: form.botName,
    takeProfit: form.takeProfit,
    useStopLoss: form.useStopLoss,
    stopLoss: form.stopLoss,
  };
}
