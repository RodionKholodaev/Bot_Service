'use client';

import { AlertCircle, Link2, Sparkles } from 'lucide-react';
import { Markdown } from './Markdown';
import { SuggestionCard } from './SuggestionCard';
import type { AssistantMessage, Suggestion } from './types';

interface Props {
  message: AssistantMessage;
  /** true — ответ ещё печатается, показываем курсор. */
  streaming: boolean;
  onApplySuggestions: (suggestions: Suggestion[]) => void;
}

const hostOf = (url: string) => {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
};

export const MessageBubble = ({
  message,
  streaming,
  onApplySuggestions,
}: Props) => {
  if (message.role === 'user') {
    return (
      <div className="ai-msg ai-msg--user">
        <div className="ai-msg__body">{message.content}</div>
      </div>
    );
  }

  return (
    <div className="ai-msg ai-msg--bot">
      <div className="ai-msg__avatar">
        <Sparkles size={13} />
      </div>

      <div className="ai-msg__body">
        {message.content && <Markdown text={message.content} />}
        {streaming && <span className="ai-caret" />}

        {message.suggestions && message.suggestions.length > 0 && (
          <SuggestionCard
            suggestions={message.suggestions}
            onApply={onApplySuggestions}
          />
        )}

        {message.sources && message.sources.length > 0 && (
          <div className="ai-sources">
            <Link2 size={12} />
            {message.sources.map((url) => (
              <a key={url} href={url} target="_blank" rel="noopener noreferrer">
                {hostOf(url)}
              </a>
            ))}
          </div>
        )}

        {message.error && (
          <div className="ai-msg__error">
            <AlertCircle size={14} />
            <span>{message.error}</span>
          </div>
        )}
      </div>
    </div>
  );
};
