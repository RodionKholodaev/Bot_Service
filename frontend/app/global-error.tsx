'use client'; // error boundary обязан быть клиентским компонентом

import { useEffect } from 'react';
import { GeistSans } from 'geist/font/sans';

/* Этот файл заменяет собой корневой layout, поэтому рисует свои <html>/<body>,
   а стили здесь инлайновые: globals.css на этом экране уже не подключён.
   Шрифт Geist подключаем сами через className — переменной --font-geist-sans
   из layout.tsx тут нет, а без неё экран рендерился бы системным шрифтом.
   Экспорт metadata тут не поддерживается — заголовок вкладки ставится
   компонентом <title>. По той же причине вёрстка нарочно простая.
   Токенов из globals.css здесь тоже нет, поэтому цвета — их копии:
   фон --bg-page, текст --text, подпись --text-secondary, иконка --text-muted,
   кнопка --accent с текстом --text-on-accent. */

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
        className={GeistSans.className}
        style={{
          margin: 0,
          minHeight: '100dvh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px',
          background: '#111626',
          color: '#e4e7f0',
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
            stroke="#6b7280"
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
              margin: '0 0 16px',
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
              padding: '12px 28px',
              background: '#3b82f6',
              border: 'none',
              borderRadius: '12px',
              color: '#fff',
              fontFamily: 'inherit',
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
