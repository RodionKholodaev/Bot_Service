"use client";
import React, { useEffect, useMemo, useRef, useState, useCallback } from "react";
import Link from "next/link";
import { Bot, LayoutGrid, TrendingUp, TrendingDown, Loader2 } from "lucide-react";
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
import { apiFetch } from "@/lib/api";

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

// ===== Types (зеркалят бэкенд schemas/stats.py) =====
type Period = "1D" | "1W" | "1M";
type ViewKey = "all" | string;

interface PnlPoint {
  ts: string;
  value: number;
}

interface TradeOut {
  id: number;
  bot_id: string;
  pair: string;
  direction: string;
  open_rate: number;
  close_rate: number | null;
  profit_usdt: number | null;
  profit_pct: number | null;
  exit_reason: string | null;
  open_time: string;
  close_time: string | null;
}

interface BotStats {
  bot_id: string;
  name: string;
  pair: string;
  leverage: number;
  direction: string;
  strategy_preset: string;
  status: string;
  total_profit: number;
  trades_total: number;
  trades_win: number;
  trades_loss: number;
  winrate: number;
  avg_profit_pct: number | null;
  max_drawdown_pct: number | null;
  pnl_chart: PnlPoint[];
  recent_trades: TradeOut[];
}

interface PortfolioStats {
  total_profit: number;
  trades_total: number;
  trades_win: number;
  trades_loss: number;
  winrate: number;
  max_drawdown_pct: number | null;
  bots_running: number;
  bots_stopped: number;
  pnl_chart: PnlPoint[];
  recent_trades: TradeOut[];
  bots: BotStats[];
}

// ===== Helpers =====
const PERIOD_LABEL: Record<Period, string> = { "1D": "1Д", "1W": "1Н", "1M": "1М" };

const formatPnl = (v: number): string => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
const formatUsdt = (v: number): string => `${v >= 0 ? "+" : ""}$${Math.abs(v).toFixed(2)}`;

const formatDuration = (open: string, close: string | null): string => {
  if (!close) return "—";
  const diff = (new Date(close).getTime() - new Date(open).getTime()) / 1000;
  const h = Math.floor(diff / 3600);
  const m = Math.floor((diff % 3600) / 60);
  return h > 0 ? `${h}ч ${m}м` : `${m}м`;
};

const formatDate = (iso: string | null): string => {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${d.getDate().toString().padStart(2, "0")}.${(d.getMonth() + 1)
    .toString()
    .padStart(2, "0")} ${d.getHours().toString().padStart(2, "0")}:${d
    .getMinutes()
    .toString()
    .padStart(2, "0")}`;
};

// ===== Component =====
const StatsPage: React.FC = () => {
  const [view, setView] = useState<ViewKey>("all");
  const [period, setPeriod] = useState<Period>("1W");
  const [portfolio, setPortfolio] = useState<PortfolioStats | null>(null);
  const [botData, setBotData] = useState<BotStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const chartRef = useRef<ChartJS<"line"> | null>(null);

  // Загрузка данных при смене вью или периода
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (view === "all") {
        const data: PortfolioStats = await apiFetch(`/stats/portfolio?period=${period}`);
        setPortfolio(data);
        setBotData(null);
      } else {
        const data: BotStats = await apiFetch(`/stats/bots/${view}?period=${period}`);
        setBotData(data);
        // Если портфель ещё не загружен — загрузим для сайдбара
        if (!portfolio) {
          const pData: PortfolioStats = await apiFetch(`/stats/portfolio?period=${period}`);
          setPortfolio(pData);
        }
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки данных");
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, period]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ===== Текущие метрики =====
  const current: PortfolioStats | BotStats | null = view === "all" ? portfolio : botData;

  const metrics = useMemo(() => {
    if (!current) return null;
    return {
      profit: current.total_profit,
      trades: current.trades_total,
      wins: current.trades_win,
      losses: current.trades_loss,
      winrate: current.winrate,
      drawdown: current.max_drawdown_pct ?? 0,
    };
  }, [current]);

  const chartSeries = useMemo(() => current?.pnl_chart ?? [], [current]);
  const trades = useMemo(() => current?.recent_trades ?? [], [current]);

  const lastValue = chartSeries.length > 0 ? chartSeries[chartSeries.length - 1].value : 0;
  const trendColor = lastValue >= 0 ? "#10b981" : "#ef4444";

  // ===== Chart configs =====
  const lineData = useMemo(() => ({
    labels: chartSeries.map((p) => p.ts),
    datasets: [
      {
        data: chartSeries.map((p) => p.value),
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
  }), [chartSeries, trendColor]);

  const lineOptions = useMemo(() => ({
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
          label: (ctx: { parsed: { y: number } }) =>
            `$${ctx.parsed.y >= 0 ? "+" : ""}${ctx.parsed.y.toFixed(2)} USDT`,
        },
      },
    },
    scales: {
      x: {
        ticks: { color: "#4b5563", font: { size: 10 }, maxTicksLimit: 8 },
        grid: { color: "rgba(255,255,255,0.04)" },
      },
      y: {
        ticks: {
          color: "#4b5563",
          font: { size: 10 },
          callback: (v: string | number) =>
            `$${Number(v) >= 0 ? "+" : ""}${Number(v).toFixed(1)}`,
        },
        grid: { color: "rgba(255,255,255,0.04)" },
      },
    },
  }), []);

  const donutData = useMemo(() => ({
    labels: ["Прибыльные", "Убыточные"],
    datasets: [
      {
        data: metrics ? [metrics.wins, metrics.losses] : [0, 0],
        backgroundColor: ["#10b981", "#ef4444"],
        borderWidth: 0,
        hoverOffset: 4,
      },
    ],
  }), [metrics]);

  const donutOptions = useMemo(() => ({
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
  }), []);

  // Данные для сайдбара всегда из portfolio
  const sidebarBots = portfolio?.bots ?? [];
  const runningCount = portfolio?.bots_running ?? 0;
  const stoppedCount = portfolio?.bots_stopped ?? 0;

  const selectedBot = view === "all" ? null : sidebarBots.find((b) => b.bot_id === view);
  const pnlClass = (metrics?.profit ?? 0) >= 0 ? "text-green" : "text-red";
  const ddClass = (metrics?.drawdown ?? 0) <= -2 ? "text-red" : "text-amber";

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
          <div className="sb-section-label">
            Боты ({sidebarBots.length})
          </div>
          {sidebarBots.map((b) => (
            <div
              key={b.bot_id}
              className={`bot-row ${view === b.bot_id ? "active" : ""}`}
              onClick={() => setView(b.bot_id)}
            >
              <div className={`bot-row-dot ${b.status === "running" ? "running" : "stopped"}`} />
              <div className="bot-row-info">
                <div className="bot-row-name">{b.pair}</div>
                <div className="bot-row-sub">
                  x{b.leverage} · {b.strategy_preset}
                </div>
              </div>
              <div
                className="bot-row-pnl"
                style={{ color: b.total_profit >= 0 ? "#10b981" : "#ef4444" }}
              >
                {formatUsdt(b.total_profit)}
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
                ? `x${selectedBot.leverage} · ${selectedBot.direction} · ${selectedBot.strategy_preset} · ${
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
                {PERIOD_LABEL[p]}
              </button>
            ))}
          </div>
        </header>

        <div className="main-body">
          {/* Loading */}
          {loading && (
            <div style={{ display: "flex", alignItems: "center", gap: 10, color: "#6b7280", padding: "40px 0" }}>
              <Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} />
              Загрузка статистики…
            </div>
          )}

          {/* Error */}
          {!loading && error && (
            <div style={{ color: "#ef4444", padding: "20px 0" }}>{error}</div>
          )}

          {/* Content */}
          {!loading && !error && metrics && (
            <>
              {/* Metrics */}
              <div className="metrics-row">
                <div className="metric-card">
                  <div className="metric-label">Общий P&L</div>
                  <div className={`metric-value ${pnlClass}`}>
                    {formatUsdt(metrics.profit)}
                  </div>
                  <div className="metric-sub">
                    {metrics.profit >= 0 ? (
                      <TrendingUp size={11} style={{ display: "inline", marginRight: 4 }} />
                    ) : (
                      <TrendingDown size={11} style={{ display: "inline", marginRight: 4 }} />
                    )}
                    За период
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
                    {metrics.drawdown !== 0 ? `${metrics.drawdown.toFixed(1)}%` : "—"}
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
                      {lastValue >= 0 ? "+" : ""}${lastValue.toFixed(2)} за период
                    </span>
                  </div>
                  <div className="chart-wrap">
                    {chartSeries.length > 0 ? (
                      <Line ref={chartRef as React.RefObject<ChartJS<"line">>} data={lineData} options={lineOptions} />
                    ) : (
                      <div className="empty-trades">Нет данных за период</div>
                    )}
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
                        <span className="legend-square" style={{ background: "#10b981" }} />
                        <span className="legend-label">Прибыльные</span>
                        <span className="legend-value text-green">{metrics.wins}</span>
                      </div>
                      <div className="donut-legend-row">
                        <span className="legend-square" style={{ background: "#ef4444" }} />
                        <span className="legend-label">Убыточные</span>
                        <span className="legend-value text-red">{metrics.losses}</span>
                      </div>
                      <div className="donut-divider">
                        <span style={{ color: "#6b7280", fontSize: 11 }}>Winrate</span>
                        <span style={{ marginLeft: "auto", fontSize: 14, fontWeight: 700, color: "#e4e7f0" }}>
                          {metrics.winrate}%
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Trades table */}
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
                        <th>P&L (USDT)</th>
                        <th>P&L (%)</th>
                        <th>Длительность</th>
                        <th>Дата</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trades.map((t) => (
                        <tr key={t.id}>
                          <td style={{ fontWeight: 600, color: "#e4e7f0" }}>{t.pair}</td>
                          <td>
                            <span className={`dir-badge ${t.direction === "long" ? "long" : "short"}`}>
                              {t.direction === "long" ? "Long" : "Short"}
                            </span>
                          </td>
                          <td>{t.open_rate.toFixed(4)}</td>
                          <td>{t.close_rate != null ? t.close_rate.toFixed(4) : "—"}</td>
                          <td style={{ fontWeight: 700, color: (t.profit_usdt ?? 0) >= 0 ? "#10b981" : "#ef4444" }}>
                            {t.profit_usdt != null ? formatUsdt(t.profit_usdt) : "—"}
                          </td>
                          <td style={{ color: (t.profit_pct ?? 0) >= 0 ? "#10b981" : "#ef4444" }}>
                            {t.profit_pct != null ? formatPnl(t.profit_pct) : "—"}
                          </td>
                          <td>{formatDuration(t.open_time, t.close_time)}</td>
                          <td style={{ color: "#4b5563" }}>{formatDate(t.close_time)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="empty-trades">Сделок пока нет</div>
                )}
              </div>
            </>
          )}
        </div>
      </main>

      <style jsx global>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
};

export default StatsPage;