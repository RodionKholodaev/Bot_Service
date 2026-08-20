'use client';

import { useEffect, useRef } from 'react';
import { RotateCcw, Sparkles, X } from 'lucide-react';
import { Composer } from './Composer';
import { MessageBubble } from './MessageBubble';
import { PhaseIndicator } from './PhaseIndicator';
import { WelcomeState } from './WelcomeState';
import { useAssistantChat } from './useAssistantChat';
import type { BotFormSnapshot, Suggestion } from './types';

interface Props {
  open: boolean;
  onClose: () => void;
  /** Текущий шаг мастера — от него зависят быстрые вопросы. */
  step: number;
  /** Читает форму в момент отправки вопроса. */
  getSnapshot: () => BotFormSnapshot;
  onApplySuggestions: (suggestions: Suggestion[]) => void;
}

/** Боковая панель ассистента. Всегда смонтирована (уезжает трансформом),
 *  поэтому диалог не теряется при закрытии. */
export const AssistantPanel = ({
  open,
  onClose,
  step,
  getSnapshot,
  onApplySuggestions,
}: Props) => {
  const chat = useAssistantChat({ getSnapshot });
  const scrollRef = useRef<HTMLDivElement>(null);

  // Держим ленту прижатой к низу, пока идёт ответ
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [chat.messages, chat.phase, open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  const lastMessage = chat.messages[chat.messages.length - 1];

  return (
    <>
      {/* Затемнение появляется только на узких экранах, где панель ложится поверх формы */}
      <div
        className={`ai-backdrop ${open ? 'is-open' : ''}`}
        onClick={onClose}
      />

      <aside
        className={`ai-panel ${open ? 'is-open' : ''}`}
        aria-hidden={!open}
      >
        <header className="ai-panel__head">
          <div className="ai-panel__title">
            <span className="ai-panel__badge">
              <Sparkles size={14} />
            </span>
            <div>
              <strong>ИИ-помощник</strong>
              <span>Видит вашу форму</span>
            </div>
          </div>

          <div className="ai-panel__actions">
            {chat.messages.length > 0 && (
              <button type="button" onClick={chat.reset} title="Начать заново">
                <RotateCcw size={15} />
              </button>
            )}
            <button type="button" onClick={onClose} title="Свернуть (Esc)">
              <X size={17} />
            </button>
          </div>
        </header>

        <div className="ai-panel__scroll" ref={scrollRef}>
          {chat.messages.length === 0 ? (
            <WelcomeState step={step} onPick={chat.send} />
          ) : (
            <div className="ai-thread">
              {chat.messages.map((message) => (
                <MessageBubble
                  key={message.id}
                  message={message}
                  streaming={
                    chat.phase === 'streaming' && message.id === lastMessage?.id
                  }
                  onApplySuggestions={onApplySuggestions}
                />
              ))}
              <PhaseIndicator
                phase={chat.phase}
                searchQuery={chat.searchQuery}
              />
            </div>
          )}
        </div>

        <Composer
          busy={chat.isBusy}
          webSearch={chat.webSearch}
          onToggleWebSearch={() => chat.setWebSearch(!chat.webSearch)}
          onSend={chat.send}
          onStop={chat.stop}
        />
      </aside>
    </>
  );
};
