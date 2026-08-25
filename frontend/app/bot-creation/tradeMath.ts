/** Расчёт того, что настройки бота значат на самом деле.
 *
 *  Проценты take profit и stop loss в форме — это движение ЦЕНЫ, и плечо на них не
 *  влияет. Влияет оно на результат: прибыль и убыток считаются от маржи (депозита,
 *  выделенного на одну сделку), а маржа в leverage раз меньше позиции. Поэтому
 *  «1.5% при x10» — это +15% депозита сделки, а не полтора процента.
 *
 *  Комиссия ломает симметрию ещё раз, и по-разному с двух сторон:
 *  freqtrade сравнивает minimal_roi с прибылью УЖЕ за вычетом комиссии, а стоп-лосс
 *  выставляет ценовым уровнем от цены входа и про комиссию не знает. Значит выигрыш
 *  равен ровно take profit, а проигрыш — стоп ПЛЮС комиссия. Отсюда и нужный винрейт.
 *
 *  Всё здесь — чистые функции без обращений к сети: числа только для показа, на
 *  торговлю они никак не влияют.
 */

/** Комиссия биржи за круг (вход + выход) в процентах от цены.
 *
 *  Не наша настройка и нигде в конфиге бота не задаётся: freqtrade берёт ставку через
 *  ccxt у самой биржи — в live из фактически исполненного ордера, в dry-run из market
 *  data. Здесь она нужна только чтобы показать порядок величины.
 *
 *  0.06% — замер по 1722 реальным сделкам. Сходится с тарифами Bybit на перпетуалах
 *  (taker 0.055%, maker 0.02%): вход у нас market, выход limit, круг ложится между
 *  0.04% и 0.11%. Сменится тариф или соотношение maker/taker — правится здесь. */
export const ROUND_TRIP_FEE_PERCENT = 0.06;

/** Доля маржи, до которой удерживается позиция без стоп-лосса.
 *  Ровно то, что уезжает в стратегию как stoploss = -0.99. */
const NO_STOP_MARGIN_PERCENT = 99;

/** Винрейт, выше которого связка настроек требует больше выигрышей, чем проигрышей. */
const WINRATE_WARNING_THRESHOLD = 50;

/** Во сколько раз take profit должен превышать комиссию, чтобы она не съедала прибыль. */
const MIN_TAKE_PROFIT_TO_FEE_RATIO = 5;

/** Доля маржи, за которой стоп подбирается к цене ликвидации. */
const DANGEROUS_STOP_MARGIN_PERCENT = 50;

export interface TradeSettings {
  /** Движение цены до take profit, % */
  takeProfitPercent: number;
  /** Движение цены до стопа, %. null — стоп не задан */
  stopLossPercent: number | null;
  leverage: number;
  /** Депозит, выделенный на одну сделку, USDT */
  marginUsdt: number;
}

export interface TradeMath {
  /** Комиссия за круг в процентах от цены */
  feePricePercent: number;
  /** Она же в процентах от маржи */
  feeMarginPercent: number;
  /** Прибыль при срабатывании take profit, % маржи */
  profitMarginPercent: number;
  /** Убыток при срабатывании стопа (с комиссией), % маржи */
  lossMarginPercent: number;
  profitUsdt: number;
  lossUsdt: number;
  /** Сколько сделок из ста должны выйти в плюс, чтобы не потерять денег */
  requiredWinrate: number;
  /** Движение цены, которое нужно пройти до take profit с учётом комиссии, % */
  effectiveTakeProfitPricePercent: number;
  /** Движение цены, на котором стоп сработает с учётом комиссии, % */
  effectiveStopPricePercent: number;
  /** Есть ли у сделки стоп вообще */
  hasStopLoss: boolean;
  /** Примерное движение цены до ликвидации, % */
  liquidationPricePercent: number;
}

/** Число из поля формы. Пустая строка, мусор, ноль и отрицательное — это «не задано». */
export function parsePositiveNumber(raw: string): number | null {
  if (raw.trim() === '') return null;
  const value = Number(raw);
  if (!Number.isFinite(value) || value <= 0) return null;
  return value;
}

export function computeTradeMath(settings: TradeSettings): TradeMath | null {
  const { takeProfitPercent, stopLossPercent, leverage, marginUsdt } = settings;

  if (!Number.isFinite(takeProfitPercent) || takeProfitPercent <= 0)
    return null;
  if (!Number.isFinite(leverage) || leverage <= 0) return null;

  const hasStopLoss = stopLossPercent !== null && stopLossPercent > 0;

  // Без стопа позиция держится до -99% маржи — это и есть её стоп, просто очень далёкий.
  // Считаем по нему же, чтобы «нет стопа» не выпадало из расчёта, а честно показывало,
  // во что обходится отсутствие стопа.
  const stopPricePercent = hasStopLoss
    ? (stopLossPercent as number)
    : NO_STOP_MARGIN_PERCENT / leverage;

  const feePricePercent = ROUND_TRIP_FEE_PERCENT;
  const feeMarginPercent = feePricePercent * leverage;

  // Выигрыш равен take profit: minimal_roi у freqtrade сравнивается с прибылью,
  // из которой комиссия уже вычтена. Значит в деньгах цель точна, а вот цене надо
  // пройти на комиссию больше, чтобы после её вычета осталось заданное.
  const profitMarginPercent = takeProfitPercent * leverage;
  const effectiveTakeProfitPricePercent = takeProfitPercent + feePricePercent;
  // Проигрыш — стоп плюс комиссия: стоп выставлен ценовым уровнем и про неё не знает.
  const effectiveStopPricePercent = stopPricePercent + feePricePercent;
  const lossMarginPercent = effectiveStopPricePercent * leverage;

  // Плечо здесь сокращается — соотношение выигрыша и проигрыша от него не зависит.
  // Это и есть главный смысл того, что проценты заданы в движении цены.
  const requiredWinrate =
    (lossMarginPercent / (profitMarginPercent + lossMarginPercent)) * 100;

  return {
    feePricePercent,
    feeMarginPercent,
    profitMarginPercent,
    lossMarginPercent,
    effectiveTakeProfitPricePercent,
    profitUsdt: (marginUsdt * profitMarginPercent) / 100,
    lossUsdt: (marginUsdt * lossMarginPercent) / 100,
    requiredWinrate,
    effectiveStopPricePercent,
    hasStopLoss,
    liquidationPricePercent: 100 / leverage,
  };
}

/** Согласование существительного с числом: 1 сделка, 2 сделки, 5 сделок. */
function pluralize(n: number, one: string, few: string, many: string): string {
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 14) return many;
  const mod10 = n % 10;
  if (mod10 === 1) return one;
  if (mod10 >= 2 && mod10 <= 4) return few;
  return many;
}

export interface TradeWarning {
  id: string;
  text: string;
}

/** Предупреждения по связке настроек. Порядок — от самого дорогого к самому дешёвому. */
export function collectTradeWarnings(
  math: TradeMath,
  settings: TradeSettings,
): TradeWarning[] {
  const warnings: TradeWarning[] = [];

  if (!math.hasStopLoss) {
    warnings.push({
      id: 'no-stop',
      text:
        `Стоп-лосс не задан: сделка будет держаться примерно до ${math.liquidationPricePercent.toFixed(1)}% ` +
        `движения цены против вас, то есть до ликвидации. Под риском весь депозит сделки.`,
    });
  }

  if (math.requiredWinrate > WINRATE_WARNING_THRESHOLD) {
    const wins = Math.round(math.requiredWinrate);
    warnings.push({
      id: 'winrate',
      text:
        `Проигрыш здесь больше выигрыша: чтобы просто не потерять денег, в плюс должны ` +
        `выходить ${wins} ${pluralize(wins, 'сделка', 'сделки', 'сделок')} из 100.`,
    });
  }

  if (
    settings.takeProfitPercent <
    ROUND_TRIP_FEE_PERCENT * MIN_TAKE_PROFIT_TO_FEE_RATIO
  ) {
    warnings.push({
      id: 'fee-heavy',
      text:
        `Take profit ${settings.takeProfitPercent}% сопоставим с комиссией за круг ` +
        `(${ROUND_TRIP_FEE_PERCENT}% цены) — она съест заметную часть прибыли.`,
    });
  }

  if (
    math.hasStopLoss &&
    math.lossMarginPercent >= DANGEROUS_STOP_MARGIN_PERCENT
  ) {
    warnings.push({
      id: 'stop-near-liquidation',
      text:
        `Стоп срабатывает при потере ${math.lossMarginPercent.toFixed(0)}% депозита сделки ` +
        `и подходит близко к ликвидации (около ${math.liquidationPricePercent.toFixed(1)}% движения цены). ` +
        `Уменьшите стоп-лосс или плечо.`,
    });
  }

  return warnings;
}
