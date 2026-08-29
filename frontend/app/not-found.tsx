import Link from 'next/link';
import './error-pages.css';

const GREEN = '#10b981';
const RED = '#ef4444';

/** Свеча графика: фитиль + полупрозрачное тело с обводкой. */
function Candle({
  x,
  wick,
  body,
  color,
}: {
  x: number;
  wick: [number, number];
  body: [number, number];
  color: string;
}) {
  return (
    <g stroke={color} fill={color}>
      <line
        x1={x}
        y1={wick[0]}
        x2={x}
        y2={wick[1]}
        strokeWidth="2"
        strokeLinecap="round"
        opacity="0.75"
      />
      <rect
        x={x - 7}
        y={body[0]}
        width="14"
        height={body[1] - body[0]}
        rx="3"
        strokeWidth="2"
        fillOpacity="0.22"
      />
    </g>
  );
}

export default function NotFound() {
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
            viewBox="0 0 690 200"
            role="img"
            aria-label="Свечной график с пропущенной свечой"
          >
            {/* Разметка графика на фоне */}
            <g stroke="rgba(255,255,255,0.06)" strokeWidth="1">
              <line x1="0" y1="18" x2="690" y2="18" />
              <line x1="0" y1="100" x2="690" y2="100" />
              <line x1="0" y1="176" x2="690" y2="176" />
              <line x1="115" y1="0" x2="115" y2="200" />
              <line x1="575" y1="0" x2="575" y2="200" />
            </g>

            <Candle x={60} wick={[60, 140]} body={[78, 125]} color={GREEN} />
            <Candle x={112} wick={[42, 150]} body={[60, 115]} color={GREEN} />
            <Candle x={163} wick={[62, 170]} body={[80, 130]} color={RED} />

            {/* Пропуск в ряду свечей — на его месте и стоит номер ошибки */}
            <rect
              x="222"
              y="32"
              width="246"
              height="138"
              rx="18"
              fill="none"
              stroke="rgba(148,163,184,0.35)"
              strokeWidth="2"
              strokeDasharray="10 8"
            />
            <text
              x="345"
              y="101"
              textAnchor="middle"
              dominantBaseline="central"
              fill="#5b6b8c"
              fontSize="62"
              fontWeight="800"
              letterSpacing="2"
              fontFamily="Inter, system-ui, sans-serif"
            >
              404
            </text>
            <circle cx="345" cy="190" r="3.5" fill="#3b82f6" />

            <Candle x={527} wick={[45, 150]} body={[62, 120]} color={GREEN} />
            <Candle x={578} wick={[65, 165]} body={[82, 132]} color={RED} />
            <Candle x={630} wick={[38, 140]} body={[55, 110]} color={GREEN} />
          </svg>
        </div>

        <span className="errpage-badge errpage-badge-blue">Ошибка 404</span>
        <h1 className="errpage-title">Страница не найдена</h1>
        <p className="errpage-subtitle">
          Такой страницы не существует или она была перемещена
        </p>

        <div className="errpage-actions">
          <Link href="/" className="errpage-btn-primary">
            На главную
          </Link>
        </div>
      </div>
    </main>
  );
}
