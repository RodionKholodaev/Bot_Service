'use client';

import { useEffect, useRef, useState } from 'react';
import { Globe, Send, Square } from 'lucide-react';

interface Props {
  busy: boolean;
  webSearch: boolean;
  onToggleWebSearch: () => void;
  onSend: (text: string) => void;
  onStop: () => void;
}

const MAX_HEIGHT = 120;

export const Composer = ({
  busy,
  webSearch,
  onToggleWebSearch,
  onSend,
  onStop,
}: Props) => {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Поле растёт под текст, но не выше MAX_HEIGHT
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT)}px`;
  }, [value]);

  const submit = () => {
    const text = value.trim();
    if (!text || busy) return;
    onSend(text);
    setValue('');
  };

  return (
    <div className="ai-composer">
      <div className="ai-composer__field">
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          placeholder="Спросите про настройки бота…"
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />

        {busy ? (
          <button
            type="button"
            className="ai-composer__stop"
            onClick={onStop}
            title="Остановить"
          >
            <Square size={14} />
          </button>
        ) : (
          <button
            type="button"
            className="ai-composer__send"
            onClick={submit}
            disabled={!value.trim()}
            title="Отправить (Enter)"
          >
            <Send size={15} />
          </button>
        )}
      </div>

      <button
        type="button"
        className={`ai-websearch ${webSearch ? 'is-on' : ''}`}
        onClick={onToggleWebSearch}
        title="Разрешить ассистенту искать актуальные данные в интернете"
      >
        <Globe size={12} />
        Поиск в интернете {webSearch ? 'вкл' : 'выкл'}
      </button>
    </div>
  );
};
