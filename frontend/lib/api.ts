// Простой API-клиент. Все запросы идут на /api/* — Next.js проксирует на бэкенд (см. next.config.ts).
// Берёт JWT из localStorage и подставляет в заголовок Authorization.

type FetchOptions = Omit<RequestInit, 'body'> & {
  body?: unknown;
  /** Что делать с 401. По умолчанию — сбросить сессию и увести на /auth.
   *  'clear-only' для страниц, открытых и гостям (гайды): протухший токен там
   *  означает «дальше как гость», а не «уходи со страницы». */
  onUnauthorized?: 'redirect' | 'clear-only';
};

/** Всё, что кладётся в localStorage при логине (app/auth/page.tsx). */
const SESSION_KEYS = ['access_token', 'user_id', 'username'];

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('access_token');
}

// Параллельных запросов на странице несколько, и протухший токен роняет их все
// разом — переход нужно инициировать один раз.
let redirectingToAuth = false;

/** Реакция на 401: чистим сессию и уводим на /auth.
 *
 *  Без этого протухший токен (живёт неделю, ACCESS_TOKEN_EXPIRE_MINUTES) оставался
 *  в localStorage, а страницы считают признаком авторизации сам факт наличия там
 *  строки. Пользователь оставался «залогиненным» на пустой странице, где все
 *  запросы молча падали в console.error, и вылечить это можно было только руками.
 *
 *  Экспортируется, потому что стрим ассистента ходит мимо apiFetch (нужен
 *  ReadableStream, а не разобранное тело) и обрабатывает свой 401 сам.
 *
 *  window.location, а не router.replace: это не компонент, роутера тут нет, а
 *  полная перезагрузка заодно выбрасывает React-стейт, набранный под старым токеном.
 */
export function clearSession(): void {
  if (typeof window === 'undefined') return;
  SESSION_KEYS.forEach((key) => localStorage.removeItem(key));
}

export function handleUnauthorized(): void {
  clearSession();
  if (typeof window === 'undefined') return;

  // Со страницы входа уводить некуда: там свой fetch и свои 401 (неверный пароль).
  if (redirectingToAuth || window.location.pathname.startsWith('/auth')) return;
  redirectingToAuth = true;
  window.location.replace('/auth');
}

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.status = status;
    this.payload = payload;
  }
}

export async function apiFetch<T = unknown>(
  path: string,
  options: FetchOptions = {},
): Promise<T> {
  const { onUnauthorized = 'redirect', ...init } = options;
  const token = getToken();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init.headers as Record<string, string> | undefined),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const url = path.startsWith('/api') ? path : `/api${path}`;

  const res = await fetch(url, {
    ...init,
    headers,
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
  });

  if (res.status === 204) {
    return undefined as T;
  }

  let payload: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  // Токен протух, был выпущен под другим SECRET_KEY или аккаунт заблокирован —
  // держать сессию дальше бессмысленно. ApiError всё равно бросаем: вызывающий
  // код не должен продолжать так, будто данные пришли.
  if (res.status === 401) {
    if (onUnauthorized === 'redirect') handleUnauthorized();
    else clearSession();
  }

  if (!res.ok) {
    const detail =
      (payload && typeof payload === 'object' && 'detail' in payload
        ? String((payload as { detail: unknown }).detail)
        : null) || `Request failed with status ${res.status}`;
    throw new ApiError(detail, res.status, payload);
  }

  return payload as T;
}
