'use client'; // error boundary обязан быть клиентским компонентом

import { useEffect } from 'react';
import Link from 'next/link';
import './error-pages.css';

/** Молния сбоку от робота: ломаная в две линии, а не залитая фигура. */
function Bolt({ x, flip = false }: { x: number; flip?: boolean }) {
  return (
    <path
      d="M 6 0 L -4 15 L 3 15 L -4 30"
      transform={`translate(${x}, 62)${flip ? ' scale(-1, 1)' : ''}`}
      fill="none"
      stroke="#fbbf24"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  );
}

export default function Error({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  useEffect(() => {
    // digest — единственная зацепка, по которой ошибку можно найти в логах сервера
    console.error(error);
  }, [error]);

  return (
    <main className="errpage">
      <div className="errpage-bg">
        <div className="errpage-glow errpage-glow-1" />
        <div className="errpage-glow errpage-glow-2" />
        <div className="errpage-grid" />
      </div>

      <div className="errpage-inner">
        <div className="errpage-art">
          <svg
            viewBox="0 0 690 230"
            role="img"
            aria-label="Сломавшийся робот над графиком"
          >
            {/* Разметка графика на фоне */}
            <g stroke="rgba(255,255,255,0.06)" strokeWidth="1">
              <line x1="0" y1="30" x2="690" y2="30" />
              <line x1="0" y1="205" x2="690" y2="205" />
              <line x1="115" y1="0" x2="115" y2="230" />
              <line x1="575" y1="0" x2="575" y2="230" />
            </g>

            {/* График: ровный ход, провал под роботом, восстановление */}
            <path
              d="M 10 182 L 60 176 L 105 180 L 150 166 L 200 170 L 245 152 L 288 156"
              fill="none"
              stroke="#10b981"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M 288 156 L 303 198 L 318 160 L 333 202 L 348 162 L 362 200 L 377 156"
              fill="none"
              stroke="#ef4444"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M 377 156 L 425 148 L 470 158 L 520 134 L 570 140 L 620 120 L 680 110"
              fill="none"
              stroke="#10b981"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            <line
              x1="285"
              y1="222"
              x2="405"
              y2="222"
              stroke="rgba(148,163,184,0.3)"
              strokeWidth="2"
              strokeDasharray="8 8"
              strokeLinecap="round"
            />

            <Bolt x={272} />
            <Bolt x={418} flip />

            {/* Робот */}
            <line
              x1="345"
              y1="20"
              x2="345"
              y2="46"
              stroke="#fbbf24"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
            <circle cx="345" cy="15" r="5" fill="#fbbf24" />
            <rect
              x="297"
              y="44"
              width="96"
              height="88"
              rx="20"
              fill="#16203a"
              stroke="#3b82f6"
              strokeWidth="2.5"
            />
            <g stroke="#94a3b8" strokeWidth="3.5" strokeLinecap="round">
              <line x1="318" y1="72" x2="330" y2="84" />
              <line x1="330" y1="72" x2="318" y2="84" />
              <line x1="360" y1="72" x2="372" y2="84" />
              <line x1="372" y1="72" x2="360" y2="84" />
              <line x1="326" y1="107" x2="364" y2="107" />
            </g>
          </svg>
        </div>

        <span className="errpage-badge errpage-badge-amber">
          Сбой интерфейса
        </span>
        <h1 className="errpage-title">Что-то пошло не так</h1>
        <p className="errpage-subtitle">
          Произошла непредвиденная ошибка. Мы уже знаем о ней. Попробуйте
          обновить страницу
        </p>

        <div className="errpage-actions">
          <Link href="/" className="errpage-btn-primary">
            На главную
          </Link>
          <button
            type="button"
            className="errpage-btn-ghost"
            onClick={() => unstable_retry()}
          >
            Обновить страницу
          </button>
        </div>

        <p className="errpage-note">
          Боты продолжают работать — сбой затронул только интерфейс
        </p>
      </div>
    </main>
  );
}
