'use client';

import { Sparkles } from 'lucide-react';

/** Готовые вопросы под текущий шаг мастера — чтобы не надо было думать,
 *  о чём вообще спрашивать ассистента. */
const PROMPTS_BY_STEP: Record<number, string[]> = {
  1: [
    'Посоветуй настройки для этого бота',
    'Сколько выделить на одну сделку?',
    'Чем Dry Run отличается от боевого?',
  ],
  2: [
    'Какую пару выбрать новичку?',
    'Какое плечо безопасно?',
    'Как снизить риск?',
  ],
  3: [
    'Посоветуй настройки для этого бота',
    'Какой индикатор для чего нужен?',
    'Как снизить риск?',
  ],
  4: [
    'Подбери Take Profit и Stop Loss',
    'Проверь мои настройки',
    'Как снизить риск?',
  ],
};

export const quickPromptsForStep = (step: number): string[] =>
  PROMPTS_BY_STEP[step] ?? PROMPTS_BY_STEP[1];

interface Props {
  step: number;
  onPick: (prompt: string) => void;
}

export const WelcomeState = ({ step, onPick }: Props) => (
  <div className="ai-welcome">
    <div className="ai-welcome__icon">
      <Sparkles size={20} />
    </div>
    <h3>Помогу собрать бота</h3>
    <p>
      Я вижу, что вы уже заполнили в форме, и подскажу конкретные значения — их
      можно применить одной кнопкой.
    </p>

    <div className="ai-welcome__prompts">
      {quickPromptsForStep(step).map((prompt) => (
        <button key={prompt} type="button" onClick={() => onPick(prompt)}>
          {prompt}
        </button>
      ))}
    </div>
  </div>
);
