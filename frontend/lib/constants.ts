import type { Indicator } from './types';

// Порог сервисного баланса в рублях: ниже него боевые боты не создаются и не
// запускаются, а работающие останавливаются сервисом (бэкенд —
// settings.MIN_SERVICE_BALANCE_RUB и services/balance_guard.py).
//
// Значение продублировано здесь намеренно: бэкенд порог наружу не отдаёт, а решение
// в любом случае принимает он — фронт лишь объясняет отказ заранее, чтобы
// пользователь не заполнял форму бота впустую. Меняя порог, поправьте оба места.
export const MIN_SERVICE_BALANCE_RUB = 100;

// Подписи пресетов стратегии для показа человеку. Сами наборы живут на бэкенде и
// приходят через GET /bots/presets — здесь только перевод ключа, который нужен там,
// где пресета целиком нет под рукой: карточка бота, статистика.
export const PRESET_LABELS: Record<string, string> = {
  conservative: 'Консервативный',
  moderate: 'Умеренный',
  aggressive: 'Агрессивный',
  custom: 'Свои настройки',
};

export const presetLabel = (key: string) => PRESET_LABELS[key] ?? key;

// Индикаторы входа. Сам список продублирован на бэкенде (FilterRule.indicator в
// backend/src/schemas/bot.py) и в шаблоне стратегии — там же зашиты периоды, поэтому
// здесь они только показываются, а не задаются. Меняя состав, правьте все места.
export interface IndicatorMeta {
  /** Короткая подпись — в выпадающем списке и в карточке бота. */
  label: string;
  /** Полное название для подсказки. */
  name: string;
  /** Период, зашитый в шаблон стратегии. */
  period: number;
  /** Одна-две фразы для человека: что показывает и как читать значения. */
  description: string;
  /** Значение нового условия: осмысленный вход для лонга на этом индикаторе. */
  defaultValue: number;
  /** Подсказка в поле значения — у индикаторов разные шкалы. */
  placeholder: string;
}

export const INDICATOR_META: Record<Indicator, IndicatorMeta> = {
  rsi: {
    label: 'RSI',
    name: 'RSI (Индекс относительной силы)',
    period: 14,
    description:
      'Показывает перекупленность или перепроданность актива. Значения ниже 30 — сигнал к покупке, выше 70 — к продаже.',
    defaultValue: 30,
    placeholder: '0–100',
  },
  cci: {
    label: 'CCI',
    name: 'CCI (Индекс товарного канала)',
    period: 20,
    description:
      'Насколько цена отклонилась от своего среднего. Ниже -100 — перепроданность (сигнал на лонг), выше +100 — перекупленность (сигнал на шорт).',
    defaultValue: -100,
    placeholder: '−200…+200',
  },
  mfi: {
    label: 'MFI',
    name: 'MFI (Индекс денежного потока)',
    period: 14,
    description:
      'То же, что RSI, но с учётом объёма торгов: показывает, куда идут деньги. Ниже 20 — перепроданность (лонг), выше 80 — перекупленность (шорт).',
    defaultValue: 20,
    placeholder: '0–100',
  },
  bb_percent: {
    label: 'Bollinger %B',
    name: 'Bollinger %B (положение цены в полосах Боллинджера)',
    period: 20,
    description:
      'Где цена внутри полос Боллинджера: 0 — на нижней полосе, 50 — посередине, 100 — на верхней. Ниже 0 или выше 100 — цена вышла за полосы.',
    defaultValue: 20,
    placeholder: '0–100',
  },
  adx: {
    label: 'ADX',
    name: 'ADX (сила тренда)',
    period: 14,
    description:
      'Сила движения без направления: ниже 20 — рынок стоит в боковике, выше 25 — идёт тренд. Ставится знаком «больше» и для лонга, и для шорта — как фильтр «торговать только в движении».',
    defaultValue: 25,
    placeholder: '0–100',
  },
};

export const INDICATOR_KEYS = Object.keys(INDICATOR_META) as Indicator[];

/** Подпись индикатора там, где ключ пришёл строкой из базы (карточка бота, чипы ИИ). */
export const indicatorLabel = (key: string) =>
  INDICATOR_META[key as Indicator]?.label ?? key.toUpperCase();
