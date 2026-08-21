'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { streamAssistantChat } from './assistantApi';
import type {
  AssistantMessage,
  AssistantPhase,
  BotFormSnapshot,
} from './types';

let messageCounter = 0;
const nextId = () => `m${++messageCounter}`;

interface Options {
  /** Вызывается в момент отправки — так ассистент видит форму такой, какая она сейчас. */
  getSnapshot: () => BotFormSnapshot;
}

/** Вся логика диалога: история, стриминг, фазы, отмена.
 *  UI-компоненты ничего не знают про SSE и просто читают это состояние. */
export function useAssistantChat({ getSnapshot }: Options) {
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [phase, setPhase] = useState<AssistantPhase>('idle');
  const [searchQuery, setSearchQuery] = useState('');
  const [webSearch, setWebSearch] = useState(false);

  const abortRef = useRef<AbortController | null>(null);

  // Актуальная история для отправки: send вызывается из обработчиков событий,
  // то есть всегда после коммита, поэтому ref успевает обновиться.
  const messagesRef = useRef<AssistantMessage[]>([]);
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  // Незавершённый запрос не должен пережить размонтирование страницы
  useEffect(() => () => abortRef.current?.abort(), []);

  const patchMessage = useCallback(
    (id: string, patch: Partial<AssistantMessage>) => {
      setMessages((prev) =>
        prev.map((m) => (m.id === id ? { ...m, ...patch } : m)),
      );
    },
    [],
  );

  const send = useCallback(
    async (text: string) => {
      const question = text.trim();
      if (!question || abortRef.current) return;

      const userMessage: AssistantMessage = {
        id: nextId(),
        role: 'user',
        content: question,
      };
      const replyId = nextId();

      // Ответ, оборвавшийся ошибкой, остаётся с пустым content. Такие пузыри
      // нельзя слать обратно: ChatMessage на бэкенде требует min_length=1,
      // и весь следующий запрос упал бы на валидации (422) — диалог был бы
      // сломан до «Начать заново».
      const history = [...messagesRef.current, userMessage]
        .filter(({ content }) => content.trim())
        .map(({ role, content }) => ({ role, content }));

      setMessages((prev) => [
        ...prev,
        userMessage,
        { id: replyId, role: 'assistant', content: '' },
      ]);
      setPhase('thinking');
      setSearchQuery('');

      const controller = new AbortController();
      abortRef.current = controller;

      // Копим текст локально: setState на каждый токен слишком дробит рендер
      let buffer = '';

      try {
        for await (const event of streamAssistantChat({
          messages: history,
          form: getSnapshot(),
          webSearch,
          signal: controller.signal,
        })) {
          switch (event.type) {
            case 'status':
              setPhase(event.stage === 'searching' ? 'searching' : 'thinking');
              setSearchQuery(
                event.stage === 'searching' ? (event.query ?? '') : '',
              );
              break;
            case 'delta':
              buffer += event.text;
              setPhase('streaming');
              patchMessage(replyId, { content: buffer });
              break;
            case 'suggestions':
              patchMessage(replyId, { suggestions: event.items });
              break;
            case 'sources':
              patchMessage(replyId, { sources: event.items });
              break;
            case 'error':
              patchMessage(replyId, {
                error: event.message,
                errorKind: event.kind ?? 'generic',
              });
              break;
            case 'done':
              break;
          }
        }
      } catch (err) {
        // AbortError — пользователь сам нажал «Стоп», это не ошибка
        if (!(err instanceof DOMException && err.name === 'AbortError')) {
          patchMessage(replyId, {
            error: 'Соединение с ассистентом прервалось.',
          });
        }
      } finally {
        abortRef.current = null;
        setPhase('idle');
        setSearchQuery('');
        // Пустой ответ без ошибки — тоже ошибка, иначе останется висеть пузырь-призрак
        setMessages((prev) =>
          prev.map((m) =>
            m.id === replyId && !m.content && !m.suggestions && !m.error
              ? {
                  ...m,
                  error:
                    'Ассистент не ответил. Попробуйте переформулировать вопрос.',
                }
              : m,
          ),
        );
      }
    },
    [getSnapshot, patchMessage, webSearch],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setMessages([]);
    setPhase('idle');
    setSearchQuery('');
  }, []);

  return {
    messages,
    phase,
    searchQuery,
    webSearch,
    setWebSearch,
    isBusy: phase !== 'idle',
    send,
    stop,
    reset,
  };
}
