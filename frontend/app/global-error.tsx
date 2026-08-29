'use client'; // error boundary обязан быть клиентским компонентом

import { useEffect } from 'react';

/* Этот файл заменяет собой корневой layout, поэтому рисует свои <html>/<body>,
   а стили здесь инлайновые: globals.css и шрифты Geist на этом экране уже не
   подключены. Экспорт metadata тут не поддерживается — заголовок вкладки
   ставится компонентом <title>. По той же причине вёрстка нарочно простая. */

const FONT = 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif';

export default function GlobalError({
  error,
}: {
  error: Error & { digest?: string };
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="ru">
      <body
        style={{
          margin: 0,
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px',
          background: '#0f1729',
          color: '#e4e7f0',
          fontFamily: FONT,
          textAlign: 'center',
        }}
      >
        <title>Сервис временно недоступен — Rudder</title>

        <div style={{ maxWidth: '420px' }}>
          <svg
            width="44"
            height="44"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#64748b"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            // корневой <svg> блочный, text-align его не центрирует
            style={{ display: 'block', margin: '0 auto 24px' }}
            role="img"
            aria-label="Робот"
          >
            <path d="M12 8V4H8" />
            <rect width="16" height="12" x="4" y="8" rx="2" />
            <path d="M2 14h2" />
            <path d="M20 14h2" />
            <path d="M9 14h6" />
          </svg>

          <h1
            style={{
              fontSize: '32px',
              fontWeight: 800,
              lineHeight: 1.15,
              letterSpacing: '-0.5px',
              margin: '0 0 14px',
            }}
          >
            Сервис временно недоступен
          </h1>

          <p
            style={{
              fontSize: '15px',
              color: '#9ca3af',
              lineHeight: 1.6,
              margin: '0 0 28px',
            }}
          >
            Попробуйте обновить страницу через минуту
          </p>

          <button
            type="button"
            onClick={() => window.location.reload()}
            style={{
              padding: '13px 26px',
              background: '#3b82f6',
              border: 'none',
              borderRadius: '12px',
              color: '#fff',
              fontFamily: FONT,
              fontSize: '15px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Обновить страницу
          </button>
        </div>
      </body>
    </html>
  );
}
