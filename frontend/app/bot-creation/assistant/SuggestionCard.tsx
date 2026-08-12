'use client';

import { useState } from 'react';
import { Check, Wand2 } from 'lucide-react';
import type { FilterRule } from '@/lib/types';
import { FIELD_META, formatFilterRule } from './fieldMeta';
import type { Suggestion } from './types';

interface Props {
  suggestions: Suggestion[];
  onApply: (suggestions: Suggestion[]) => void;
}

/** Карточка с конкретными значениями полей, которые ассистент предлагает поставить.
 *  Пользователь применяет всё разом или по одному пункту. */
export const SuggestionCard = ({ suggestions, onApply }: Props) => {
  const [applied, setApplied] = useState<Set<string>>(new Set());

  const applyOne = (suggestion: Suggestion) => {
    onApply([suggestion]);
    setApplied((prev) => new Set(prev).add(suggestion.field));
  };

  const applyAll = () => {
    onApply(suggestions);
    setApplied(new Set(suggestions.map((s) => s.field)));
  };

  const allApplied = suggestions.every((s) => applied.has(s.field));

  return (
    <div className="ai-suggestions">
      <div className="ai-suggestions__head">
        <Wand2 size={14} />
        <span>Предлагаю настройки</span>
      </div>

      <div className="ai-suggestions__list">
        {suggestions.map((suggestion) => {
          const meta = FIELD_META[suggestion.field];
          if (!meta) return null;
          const isApplied = applied.has(suggestion.field);

          return (
            <div key={suggestion.field} className="ai-suggestion">
              <div className="ai-suggestion__row">
                <span className="ai-suggestion__label">{meta.label}</span>
                <span className="ai-suggestion__value">{meta.format(suggestion.value)}</span>
                <button
                  type="button"
                  className={`ai-suggestion__apply ${isApplied ? 'is-applied' : ''}`}
                  onClick={() => applyOne(suggestion)}
                  disabled={isApplied}
                >
                  {isApplied ? <Check size={13} /> : 'Применить'}
                </button>
              </div>

              {suggestion.field === 'filters' && Array.isArray(suggestion.value) && (
                <div className="ai-suggestion__rules">
                  {(suggestion.value as FilterRule[]).map((rule, i) => (
                    <span key={i} className={`ai-rule ai-rule--${rule.indicator}`}>
                      {formatFilterRule(rule)}
                    </span>
                  ))}
                </div>
              )}

              {suggestion.reason && <p className="ai-suggestion__reason">{suggestion.reason}</p>}
            </div>
          );
        })}
      </div>

      {suggestions.length > 1 && (
        <button
          type="button"
          className="ai-suggestions__apply-all"
          onClick={applyAll}
          disabled={allApplied}
        >
          {allApplied ? 'Применено' : 'Применить всё'}
        </button>
      )}
    </div>
  );
};
