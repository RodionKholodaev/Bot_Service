"use client";
import React, { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  Bot,
  LayoutGrid,
  TrendingUp,
  TrendingDown,
  Activity,
  Circle,
} from "lucide-react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Filler,
  Tooltip,
  Legend,
} from "chart.js";
import { Line, Doughnut } from "react-chartjs-2";
import "./stats.css";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Filler,
  Tooltip,
  Legend
);

// ===== Types =====
type BotStatus = "running" | "stopped";
type Direction = "Long" | "Short" | "Both";

interface BotInfo {
  id: string;
  pair: string;
  leverage: string;
  direction: Direction;
  status: BotStatus;
  pnl: number;
  trades: number;
  wins: number;
  strategy: string;
}

interface Trade {
  pair: string;
  direction: "Long" | "Short";
  entry: string;
  exit: string;
  pnl: number;
  duration: string;
  date: string;
}

type Period = "1D" | "1W" | "1M";
type ViewKey = "all" | string;

// ===== Mock data (replace with real API later) =====
const BOTS: BotInfo[] = [
  {
    id: "bot0",
    pair: "BTC/USDT",
    leverage: "x10",
    direction: "Long",
    status: "running",
    pnl: 6.4,
    trades: 38,
    wins: 25,
    strategy: "RSI + CCI",
  },
  {
    id: "bot1",
    pair: "ETH/USDT",
    leverage: "x5",
    direction: "Both",
    status: "running",
    pnl: 2.1,
    trades: 52,
    wins: 30,
    strategy: "RSI",
  },
  {
    id: "bot2",
    pair: "SOL/USDT",
    leverage: "x3",
    direction: "Short",
    status: "stopped",
    pnl: -1.2,
    trades: 19,
    wins: 8,
    strategy: "CCI",
  },
];

const ALL_TRADES: Trade[] = [
  { pair: "BTC/USDT", direction: "Long", entry: "62,440", exit: "64,110", pnl: 2.7, duration: "2ч 14м", date: "27.04 12:31" },
  { pair: "ETH/USDT", direction: "Long", entry: "2,890", exit: "3,020", pnl: 4.5, duration: "4ч 02м", date: "27.04 10:14" },
  { pair: "SOL/USDT", direction: "Short", entry: "148.2", exit: "151.0", pnl: -1.9, duration: "1ч 38м", date: "26.04 22:05" },
  { pair: "BTC/USDT", direction: "Long", entry: "61,800", exit: "62,300", pnl: 0.8, duration: "55м", date: "26.04 18:40" },
  { pair: "ETH/USDT", direction: "Short", entry: "3,100", exit: "3,060", pnl: 1.3, duration: "3ч 21м", date: "26.04 14:22" },
  { pair: "BTC/USDT", direction: "Long", entry: "60,500", exit: "59,800", pnl: -1.2, duration: "1ч 07м", date: "25.04 09:17" },
  { pair: "SOL/USDT", direction: "Short", entry: "145.0", exit: "143.5", pnl: 1.0, duration: "2ч 45м", date: "25.04 07:50" },
];

// P&L series for chart
const CHART_DATA: Record<Period, Record<string, number[]>> = {
  "1D": {
    all: [0, 0.4, 0.9, 1.3, 1.0, 1.7, 2.3, 3.0, 3.4, 3.1, 3.8, 4.4, 5.0, 5.6, 6.0, 6.4, 7.1, 7.6, 7.3, 7.6, 7.3, 7.5, 7.2, 7.4],
    bot0: [0, 0.2, 0.6, 1.1, 0.9, 1.4, 2.1, 2.6, 3.0, 2.7, 3.3, 3.8, 4.3, 5.0, 5.3, 5.7, 6.2, 6.4],
    bot1: [0, 0.1, 0.3, 0.5, 0.4, 0.6, 0.9, 1.1, 1.3, 1.5, 1.2, 1.6, 1.9, 2.1, 2.0, 2.1],
    bot2: [0, -0.1, -0.2, -0.3, -0.4, -0.5, -0.7, -0.8, -1.0, -1.1, -1.2],
  },
  "1W": {
    all: [0, 1.2, 0.8, 2.4, 1.8, 3.2, 4.1, 7.4],
    bot0: [0, 0.8, 0.5, 1.5, 1.2, 2.3, 3.1, 6.4],
    bot1: [0, 0.5, 0.4, 0.9, 0.7, 1.1, 1.5, 2.1],
    bot2: [0, -0.1, -0.2, -0.4, -0.5, -0.8, -1.0, -1.2],
  },
  "1M": {
    all: [0, 1.5, 1, 3, 2.5, 5, 4, 7, 6, 8, 7, 9.5, 8.5, 10, 9, 11, 10, 12, 11, 7.4],
    bot0: [0, 1, 0.5, 2, 1.5, 3, 2.5, 4, 3.5, 5, 4.5, 6.4],
    bot1: [0, 0.5, 0.3, 1, 0.8, 1.5, 1.2, 2, 1.7, 2.1],
    bot2: [0, -0.1, -0.2, -0.3, -0.5, -0.6, -0.8, -0.9, -1, -1.1, -1.2],
  },
};

const buildLabels = (period: Period, length: number): string[] => {
  if (period === "1D") return Array.from({ length }, (_, i) => `${i}:00`);
  if (period === "1W") return ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс", ""].slice(0, length);
  return Array.from({ length }, (_, i) => `${i + 1}`);
};

const formatPnl = (v: number): string => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`;

// ===== Component =====
const StatsPage: React.FC = () => {
  const [view, setView] = useState<ViewKey>("all");
  const [period, setPeriod] = useState<Period>("1D");
  const chartRef = useRef<ChartJS<"line"> | null>(null);

  const selectedBot = useMemo(
    () => (view === "all" ? null : BOTS.find((b) => b.id === view) ?? null),
    [view]
  );

  const metrics = useMemo(() => {
    if (view === "all") {
      const totalPnl = 7.4;
      const totalTrades = BOTS.reduce((s, b) => s + b.trades, 0);
      const totalWins = BOTS.reduce((s, b) => s + b.wins, 0);
      return {
        pnl: totalPnl,
        trades: totalTrades,
        wins: totalWins,
        losses: totalTrades - totalWins,
        winrate: Math.round((totalWins / totalTrades) * 100),
        drawdown: -3.1,
      };
    }
    const b = selectedBot!;
    const losses = b.trades - b.wins;
    return {
      pnl: b.pnl,
      trades: b.trades,
      wins: b.wins,
      losses,
      winrate: Math.round((b.wins / b.trades) * 100),
      drawdown: b.pnl < 0 ? b.pnl : -Math.abs(b.pnl) * 0.35,
    };
  }, [view, selectedBot]);

  const trades = useMemo(() => {
    if (view === "all") return ALL_TRADES;
    if (!selectedBot) return [];
    return ALL_TRADES.filter((t) => t.pair === selectedBot.pair);
  }, [view, selectedBot]);

  const chartSeries = useMemo(() => {
    const key = view === "all" ? "all" : view;
    return CHART_DATA[period][key] ?? CHART_DATA[period].all;
  }, [view, period]);

  const lastValue = chartSeries[chartSeries.length - 1] ?? 0;
  const trendColor = lastValue >= 0 ? "#10b981" : "#ef4444";

  // ===== Chart configs =====
  const lineData = useMemo(
    () => ({
      labels: buildLabels(period, chartSeries.length),
      datasets: [
        {
          data: chartSeries,
          borderColor: trendColor,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: trendColor,
          pointHoverBorderColor: "#0b1220",
          pointHoverBorderWidth: 2,
          fill: true,
          backgroundColor: (ctx: { chart: ChartJS }) => {
            const c = ctx.chart.ctx;
            if (!c) return trendColor + "20";
            const g = c.createLinearGradient(0, 0, 0, 200);
            g.addColorStop(0, trendColor + "40");
            g.addColorStop(1, trendColor + "00");
            return g;
          },
          tension: 0.4,
        },
      ],
    }),
    [chartSeries, trendColor, period]
  );

  const lineOptions = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(15, 23, 41, 0.95)",
          borderColor: "rgba(255,255,255,0.1)",
          borderWidth: 1,
          padding: 10,
          titleColor: "#9ca3af",
          bodyColor: "#e4e7f0",
          callbacks: {
            label: (ctx: { parsed: { y: number } }) => formatPnl(ctx.parsed.y),
          },
        },
      },
      scales: {
        x: {
          ticks: { color: "#4b5563", font: { size: 10 }, maxTicksLimit: 10 },
          grid: { color: "rgba(255,255,255,0.04)" },
        },
        y: {
          ticks: {
            color: "#4b5563",
            font: { size: 10 },
            callback: (v: string | number) => formatPnl(Number(v)),
          },
          grid: { color: "rgba(255,255,255,0.04)" },
        },
      },
    }),
    []
  );

  const donutData = useMemo(
    () => ({
      labels: ["Прибыльные", "Убыточные"],
      datasets: [
        {
          data: [metrics.wins, metrics.losses],
          backgroundColor: ["#10b981", "#ef4444"],
          borderWidth: 0,
          hoverOffset: 4,
        },
      ],
    }),
    [metrics.wins, metrics.losses]
  );

  const donutOptions = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      cutout: "72%",
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(15, 23, 41, 0.95)",
          borderColor: "rgba(255,255,255,0.1)",
          borderWidth: 1,
          padding: 10,
          titleColor: "#9ca3af",
          bodyColor: "#e4e7f0",
        },
      },
    }),
    []
  );

  const runningCount = BOTS.filter((b) => b.status === "running").length;
  const stoppedCount = BOTS.length - runningCount;

  const pnlClass = metrics.pnl >= 0 ? "text-green" : "text-red";
  const ddClass = metrics.drawdown <= -2 ? "text-red" : "text-amber";

  return (
    <div className="stats-page">
      {/* ===== SIDEBAR ===== */}
      <aside className="stats-sidebar">
        <div className="sb-header">
          <Link href="/" className="sb-logo">
            <span className="sb-logo-icon">
              <Bot size={15} />
            </span>
            CryptoBot
          </Link>
          <div className="sb-section-label">Портфель</div>
          <button
            className={`sb-all-btn ${view === "all" ? "active" : ""}`}
            onClick={() => setView("all")}
          >
            <LayoutGrid size={14} />
            Все боты
          </button>
        </div>

        <div className="sb-bots">
          <div className="sb-section-label">Активные ({BOTS.length})</div>
          {BOTS.map((b) => (
            <div
              key={b.id}
              className={`bot-row ${view === b.id ? "active" : ""}`}
              onClick={() => setView(b.id)}
            >
              <div className={`bot-row-dot ${b.status}`} />
              <div className="bot-row-info">
                <div className="bot-row-name">{b.pair}</div>
                <div className="bot-row-sub">
                  {b.leverage} · {b.strategy}
                </div>
              </div>
              <div
                className="bot-row-pnl"
                style={{ color: b.pnl >= 0 ? "#10b981" : "#ef4444" }}
              >
                {formatPnl(b.pnl)}
              </div>
            </div>
          ))}
        </div>

        <div className="sb-footer">
          <div className="sb-footer-row">
            <div className="sb-status-dot" />
            {runningCount} активных · {stoppedCount} остановлен
            {stoppedCount === 1 ? "" : "ых"}
          </div>
        </div>
      </aside>

      {/* ===== MAIN ===== */}
      <main className="stats-main">
        <header className="main-header">
          <div>
            <div className="view-title">
              {selectedBot ? selectedBot.pair : "Все боты"}
            </div>
            <div className="view-subtitle">
              {selectedBot
                ? `${selectedBot.leverage} · ${selectedBot.direction} · ${selectedBot.strategy} · ${
                    selectedBot.status === "running" ? "Работает" : "Остановлен"
                  }`
                : "Общая статистика портфеля"}
            </div>
          </div>
          <div className="header-period">
            {(["1D", "1W", "1M"] as Period[]).map((p) => (
              <button
                key={p}
                className={`period-tab ${period === p ? "active" : ""}`}
                onClick={() => setPeriod(p)}
              >
                {p === "1D" ? "1Д" : p === "1W" ? "1Н" : "1М"}
              </button>
            ))}
          </div>
        </header>

        <div className="main-body">
          {/* Metrics */}
          <div className="metrics-row">
            <div className="metric-card">
              <div className="metric-label">Общий P&L</div>
              <div className={`metric-value ${pnlClass}`}>
                {formatPnl(metrics.pnl)}
              </div>
              <div className="metric-sub">
                {metrics.pnl >= 0 ? (
                  <TrendingUp size={11} style={{ display: "inline", marginRight: 4 }} />
                ) : (
                  <TrendingDown size={11} style={{ display: "inline", marginRight: 4 }} />
                )}
                За всё время
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Winrate</div>
              <div className="metric-value text-white">{metrics.winrate}%</div>
              <div className="metric-bar">
                <div
                  className="metric-bar-fill"
                  style={{ width: `${metrics.winrate}%` }}
                />
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Всего сделок</div>
              <div className="metric-value text-blue">{metrics.trades}</div>
              <div className="metric-sub">
                {metrics.wins} прибыль · {metrics.losses} убыток
              </div>
            </div>

            <div className="metric-card">
              <div className="metric-label">Макс. просадка</div>
              <div className={`metric-value ${ddClass}`}>
                {metrics.drawdown.toFixed(1)}%
              </div>
              <div className="metric-sub">За период</div>
            </div>
          </div>

          {/* Charts */}
          <div className="charts-row">
            <div className="stats-card">
              <div className="card-head">
                <span className="card-label">P&L по времени</span>
                <span
                  className="card-note"
                  style={{ color: trendColor, fontWeight: 600 }}
                >
                  {formatPnl(lastValue)} за период
                </span>
              </div>
              <div className="chart-wrap">
                <Line ref={chartRef as React.RefObject<ChartJS<"line">>} data={lineData} options={lineOptions} />
              </div>
            </div>

            <div className="stats-card">
              <div className="card-head">
                <span className="card-label">Распределение сделок</span>
                <span className="card-note">
                  {metrics.wins} побед · {metrics.losses} убытков
                </span>
              </div>
              <div className="donut-row">
                <div className="donut-canvas-wrap">
                  <Doughnut data={donutData} options={donutOptions} />
                </div>
                <div className="donut-legend">
                  <div className="donut-legend-row">
                    <span
                      className="legend-square"
                      style={{ background: "#10b981" }}
                    />
                    <span className="legend-label">Прибыльные</span>
                    <span className="legend-value text-green">
                      {metrics.wins}
                    </span>
                  </div>
                  <div className="donut-legend-row">
                    <span
                      className="legend-square"
                      style={{ background: "#ef4444" }}
                    />
                    <span className="legend-label">Убыточные</span>
                    <span className="legend-value text-red">
                      {metrics.losses}
                    </span>
                  </div>
                  <div className="donut-divider">
                    <span style={{ color: "#6b7280", fontSize: 11 }}>
                      Winrate
                    </span>
                    <span
                      style={{
                        marginLeft: "auto",
                        fontSize: 14,
                        fontWeight: 700,
                        color: "#e4e7f0",
                      }}
                    >
                      {metrics.winrate}%
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Trades */}
          <div className="stats-card">
            <div className="card-head">
              <span className="card-label">Последние сделки</span>
              <span className="card-note">{trades.length} сделок</span>
            </div>
            {trades.length > 0 ? (
              <table className="trades-table">
                <thead>
                  <tr>
                    <th>Пара</th>
                    <th>Направление</th>
                    <th>Вход</th>
                    <th>Выход</th>
                    <th>P&L</th>
                    <th>Длительность</th>
                    <th>Дата</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map((t, i) => (
                    <tr key={i}>
                      <td style={{ fontWeight: 600, color: "#e4e7f0" }}>
                        {t.pair}
                      </td>
                      <td>
                        <span
                          className={`dir-badge ${
                            t.direction === "Long" ? "long" : "short"
                          }`}
                        >
                          {t.direction}
                        </span>
                      </td>
                      <td>{t.entry}</td>
                      <td>{t.exit}</td>
                      <td
                        style={{
                          fontWeight: 700,
                          color: t.pnl >= 0 ? "#10b981" : "#ef4444",
                        }}
                      >
                        {formatPnl(t.pnl)}
                      </td>
                      <td>{t.duration}</td>
                      <td style={{ color: "#4b5563" }}>{t.date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="empty-trades">Сделок пока нет</div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default StatsPage;