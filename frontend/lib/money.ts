/** Знак суммы после округления до `digits` знаков: 1, -1 или 0.
 *  Сравниваем округлённое значение, иначе -0.004 показалось бы как «-$0.00» красным. */
export function moneySign(v: number, digits = 2): 1 | -1 | 0 {
  const r = Number(v.toFixed(digits));
  return r > 0 ? 1 : r < 0 ? -1 : 0;
}

/** «+$1.50», «-$1.50», «$0.00»: у нуля нет знака, иначе он читается как прибыль. */
export function formatSignedUsd(v: number, digits = 2): string {
  const s = moneySign(v, digits);
  return `${s > 0 ? '+' : s < 0 ? '-' : ''}$${Math.abs(v).toFixed(digits)}`;
}

/** Класс цвета для суммы со знаком. Ноль — без цвета: он не прибыль и не убыток. */
export function profitClass(v: number): 'profit' | 'loss' | '' {
  const s = moneySign(v);
  return s > 0 ? 'profit' : s < 0 ? 'loss' : '';
}
