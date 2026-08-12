'use client';

import { Globe, Sparkles } from 'lucide-react';
import type { AssistantPhase } from './types';

interface Props {
  phase: AssistantPhase;
  searchQuery: string;
}

/** «Печатает» / «Ищет в интернете» — состояние ассистента между вопросом и текстом.
 *  Во время streaming ничего не показываем: там уже бежит сам текст с курсором. */
export const PhaseIndicator = ({ phase, searchQuery }: Props) => {
  if (phase === 'idle' || phase === 'streaming') return null;

  const searching = phase === 'searching';

  return (
    <div className={`ai-phase ${searching ? 'ai-phase--search' : ''}`}>
      <span className="ai-phase__icon">
        {searching ? <Globe size={13} /> : <Sparkles size={13} />}
      </span>

      <span className="ai-phase__text">
        {searching ? 'Ищу в интернете' : 'Думаю'}
        {searching && searchQuery && <em>«{searchQuery}»</em>}
      </span>

      <span className="ai-dots">
        <i />
        <i />
        <i />
      </span>
    </div>
  );
};
