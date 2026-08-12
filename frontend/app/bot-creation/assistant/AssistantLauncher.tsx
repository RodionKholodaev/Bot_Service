'use client';

import { useEffect, useState } from 'react';
import { Sparkles, X } from 'lucide-react';

const HINT_SEEN_KEY = 'assistant_hint_seen';
const HINT_TIMEOUT_MS = 9000;

interface Props {
  open: boolean;
  onOpen: () => void;
}

/** Вкладка у правого края страницы. Свёрнутая занимает ~40px и не спорит с формой,
 *  но подписана словами, так что понятно, что это и зачем.
 *  При первом заходе один раз показывает подсказку — дальше молчит. */
export const AssistantLauncher = ({ open, onOpen }: Props) => {
  const [showHint, setShowHint] = useState(false);

  useEffect(() => {
    if (open || localStorage.getItem(HINT_SEEN_KEY)) return;
    const show = setTimeout(() => setShowHint(true), 900);
    const hide = setTimeout(() => setShowHint(false), 900 + HINT_TIMEOUT_MS);
    return () => {
      clearTimeout(show);
      clearTimeout(hide);
    };
  }, [open]);

  const dismissHint = () => {
    setShowHint(false);
    localStorage.setItem(HINT_SEEN_KEY, '1');
  };

  return (
    <div className={`ai-launcher ${open ? 'is-hidden' : ''}`} aria-hidden={open}>
      {showHint && (
        <div className="ai-launcher__hint">
          <button type="button" className="ai-launcher__hint-close" onClick={dismissHint}>
            <X size={12} />
          </button>
          <strong>Не знаете, что выбрать?</strong>
          <span>ИИ-помощник видит вашу форму и подскажет конкретные значения.</span>
        </div>
      )}

      <button
        type="button"
        className="ai-launcher__tab"
        onClick={() => {
          dismissHint();
          onOpen();
        }}
        title="Открыть ИИ-помощника"
      >
        <Sparkles size={16} />
        <span className="ai-launcher__label">ИИ-помощник</span>
      </button>
    </div>
  );
};
