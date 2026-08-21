import type {
  AssistantEvent,
  AssistantMessage,
  BotFormSnapshot,
} from './types';

/** Транспорт ассистента.
 *
 *  Отдельно от lib/api.ts, потому что там fetch читает тело целиком, а тут нужен
 *  поток. EventSource не подходит — он не умеет POST и заголовок Authorization. */

function authHeaders(): Record<string, string> {
  const token =
    typeof window === 'undefined' ? null : localStorage.getItem('access_token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

/** Включён ли ассистент на бэкенде (задан ли ключ AITunnel). */
export async function fetchAssistantStatus(): Promise<{
  enabled: boolean;
  web_search_available: boolean;
}> {
  const res = await fetch('/api/assistant/status', { headers: authHeaders() });
  if (!res.ok) return { enabled: false, web_search_available: false };
  return res.json();
}

/** Разбирает SSE-поток в отдельные `data:`-строки. */
async function* readSseLines(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<string> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // События разделены пустой строкой
      let boundary = buffer.indexOf('\n\n');
      while (boundary !== -1) {
        const raw = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        for (const line of raw.split('\n')) {
          if (line.startsWith('data:')) yield line.slice(5).trim();
        }
        boundary = buffer.indexOf('\n\n');
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export interface StreamChatParams {
  messages: Pick<AssistantMessage, 'role' | 'content'>[];
  form: BotFormSnapshot;
  webSearch: boolean;
  signal: AbortSignal;
}

/** Отправляет вопрос и отдаёт события ответа по мере их прихода. */
export async function* streamAssistantChat(
  params: StreamChatParams,
): AsyncGenerator<AssistantEvent> {
  const res = await fetch('/api/assistant/chat', {
    method: 'POST',
    headers: authHeaders(),
    signal: params.signal,
    body: JSON.stringify({
      messages: params.messages,
      form: params.form,
      web_search: params.webSearch,
    }),
  });

  if (!res.ok || !res.body) {
    let detail = 'Ассистент недоступен. Попробуйте позже.';
    try {
      const payload = await res.json();
      // У доменных ошибок detail — строка, а у 422 от FastAPI — массив объектов,
      // который String() показал бы пользователю как «[object Object]».
      if (typeof payload?.detail === 'string') detail = payload.detail;
    } catch {
      /* тело не JSON — оставляем текст по умолчанию */
    }
    yield {
      type: 'error',
      message: detail,
      kind: res.status === 429 ? 'rate_limit' : 'generic',
    };
    yield { type: 'done' };
    return;
  }

  for await (const chunk of readSseLines(res.body)) {
    if (!chunk) continue;
    try {
      yield JSON.parse(chunk) as AssistantEvent;
    } catch {
      /* битый кадр пропускаем — поток продолжается */
    }
  }
}
