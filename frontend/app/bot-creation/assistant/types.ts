import type { FilterRule } from '@/lib/types';

/** Поля формы создания бота, которые ассистенту разрешено предлагать.
 *  Список синхронизирован с SUGGESTABLE_FIELDS в backend/src/services/assistant/tools.py. */
export type SuggestableField =
  | 'dryRun'
  | 'stakeAmount'
  | 'balanceRatio'
  | 'tradingPair'
  | 'leverage'
  | 'algorithm'
  | 'strategyPreset'
  | 'filters'
  | 'botName'
  | 'takeProfit'
  | 'useStopLoss'
  | 'stopLoss';

/** Одно предложение ассистента: «поставь сюда вот это, потому что...». */
export interface Suggestion {
  field: SuggestableField;
  value: string | number | boolean | FilterRule[];
  reason: string;
}

export type AssistantPhase = 'idle' | 'thinking' | 'searching' | 'streaming';

/** Упёрлись в лимит запросов (429) — это норма, а не поломка,
 *  и показывается спокойнее обычной ошибки. */
export type AssistantErrorKind = 'rate_limit' | 'generic';

export interface AssistantMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  suggestions?: Suggestion[];
  sources?: string[];
  /** Заполняется, если ответ оборвался ошибкой. */
  error?: string;
  errorKind?: AssistantErrorKind;
}

/** События SSE-потока из POST /api/assistant/chat. */
export type AssistantEvent =
  | { type: 'status'; stage: 'thinking' | 'searching'; query?: string }
  | { type: 'delta'; text: string }
  | { type: 'suggestions'; items: Suggestion[] }
  | { type: 'sources'; items: string[] }
  | { type: 'error'; message: string; kind?: AssistantErrorKind }
  | { type: 'done' };

/** Снимок мастера создания бота — то, что ассистент «видит» на экране.
 *  Имена полей совпадают с formData в page.tsx, чтобы применение
 *  предложений не требовало никакого маппинга. */
export interface BotFormSnapshot {
  step: number;
  dryRun: boolean;
  stakeAmount: string;
  balanceRatio: string;
  hasApiKeys: boolean;
  tradingPair: string;
  leverage: string;
  algorithm: string;
  strategyPreset: string;
  filters: FilterRule[];
  botName: string;
  takeProfit: string;
  useStopLoss: boolean;
  stopLoss: string;
}
