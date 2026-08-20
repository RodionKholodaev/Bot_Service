"use client";
import React, { useEffect, useMemo, useRef, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from 'next/navigation';
import type { TooltipItem } from 'chart.js';
import {
  Zap,
  Settings,
  CreditCard,
  LayoutGrid,
  TrendingUp,
  TrendingDown,
  Target,
  Activity,
  ArrowDownRight,
  AlertTriangle,
  Loader2,
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
  ts: string;   // ISO-время закрытия сделки (UTC), формат выбираем здесь
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

// Строка бота в сайдбаре. Отдельный тип, а не BotStats: портфель не тащит на каждого
// бота его график и последние сделки — сайдбару они не нужны.
interface BotSummary {
  bot_id: string;
  name: string;
  pair: string;
  leverage: number;
  direction: string;
  strategy_preset: string;
  status: string;
  profit: number;        // за выбранный период
  trades_total: number;
  winrate: number;
}

interface BotStats {
  bot_id: string;
  name: string;
  pair: string;
  leverage: number;
  direction: string;
  strategy_preset: string;
  status: string;
  profit: number;        // за выбранный период, а не за всё время
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
  profit: number;        // за выбранный период
  trades_total: number;
  trades_win: number;
  trades_loss: number;
  winrate: number;
  max_drawdown_pct: number | null;
  bots_running: number;
  bots_stopped: number;
  pnl_chart: PnlPoint[];
  recent_trades: TradeOut[];
  bots: BotSummary[];
}

// ===== Helpers =====
const PERIOD_LABEL: Record<Period, string> = { "1D": "1Д", "1W": "1Н", "1M": "1М" };

// Палитра графиков — из общей схемы сайта (см. /home, /feedback)
const COLOR_GREEN = "#34d399";
const COLOR_RED = "#f87171";

const formatPnl = (v: number): string => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
// Знак ставим перед $, минус — обязательно: без него убыток выглядел бы как прибыль
const formatUsdt = (v: number): string => `${v >= 0 ? "+" : "-"}$${Math.abs(v).toFixed(2)}`;

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

// тот же светофор баланса, что на главной и в обратной связи
const getBalanceStatus = (balance: number): string => {
  if (balance < 100) return "critical";
  if (balance < 1000) return "low";
  return "good";
};

// ===== Component =====
const StatsPage: React.FC = () => {
  const router = useRouter();
  const [view, setView] = useState<ViewKey>("all");
  const [period, setPeriod] = useState<Period>("1W");
  const [portfolio, setPortfolio] = useState<PortfolioStats | null>(null);
  const [botData, setBotData] = useState<BotStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const chartRef = useRef<ChartJS<"line"> | null>(null);
  const [isAuthed, setIsAuthed] = useState(false);
  const [serviceBalance, setServiceBalance] = useState<number>(0);

  // проверка того что пользователь имеет JWT
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.replace('/auth');
    } else {
      setIsAuthed(true); // ← добавь
    }
  }, [router]);

  // Баланс нужен только для индикатора в шапке — той же, что на /home и /feedback
  const fetchBalance = useCallback(async () => {
    try {
      const data = await apiFetch<{ service_balance: number }>("/users/me/balance");
      setServiceBalance(data.service_balance);
    } catch (e) {
      console.error("Не удалось загрузить баланс:", e);
    }
  }, []);

  useEffect(() => {
    if (!isAuthed) return;
    fetchBalance();
  }, [isAuthed, fetchBalance]);

  // Загрузка данных при смене вью или периода
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Портфель запрашиваем всегда: числа в сайдбаре считаются за выбранный период,
      // поэтому при смене периода они устаревают, даже когда открыт отдельный бот.
      const [pData, bData] = await Promise.all([
        apiFetch<PortfolioStats>(`/stats/portfolio?period=${period}`),
        view === "all"
          ? Promise.resolve(null)
          : apiFetch<BotStats>(`/stats/bots/${view}?period=${period}`),
      ]);
      setPortfolio(pData);
      setBotData(bData);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Ошибка загрузки данных");
    } finally {
      setLoading(false);
    }
  }, [view, period]);

  useEffect(() => {
    if (!isAuthed) return;
    fetchData();
  }, [isAuthed, fetchData]);

  // ===== Текущие метрики =====
  const current: PortfolioStats | BotStats | null = view === "all" ? portfolio : botData;

  const metrics = useMemo(() => {
    if (!current) return null;
    return {
      profit: current.profit,
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
  const trendColor = lastValue >= 0 ? COLOR_GREEN : COLOR_RED;

  // ===== Chart configs =====
  const lineData = useMemo(() => ({
    labels: chartSeries.map((p) => formatDate(p.ts)),
    datasets: [
      {
        data: chartSeries.map((p) => p.value),
        borderColor: trendColor,
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 4,
        pointHoverBackgroundColor: trendColor,
        pointHoverBorderColor: "#0a0e1a",
        pointHoverBorderWidth: 2,
        fill: true,
        backgroundColor: (ctx: { chart: ChartJS }) => {
          const c = ctx.chart.ctx;
          if (!c) return trendColor + "20";
          const g = c.createLinearGradient(0, 0, 0, 220);
          g.addColorStop(0, trendColor + "45");
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
        backgroundColor: "rgba(26, 31, 53, 0.95)",
        borderColor: "rgba(96, 165, 250, 0.25)",
        borderWidth: 1,
        padding: 10,
        titleColor: "#9ca3af",
        bodyColor: "#e4e7f0",
        callbacks: {
          label: (ctx: TooltipItem<'line'>) => {
            const y = ctx.parsed.y ?? 0;
            return `$${y >= 0 ? "+" : ""}${y.toFixed(2)} USDT`;
          }
        },
      },
    },
    scales: {
      x: {
        ticks: { color: "#6b7280", font: { size: 10 }, maxTicksLimit: 8 },
        grid: { color: "rgba(255,255,255,0.05)" },
      },
      y: {
        ticks: {
          color: "#6b7280",
          font: { size: 10 },
          callback: (v: string | number) =>
            `$${Number(v) >= 0 ? "+" : ""}${Number(v).toFixed(1)}`,
        },
        grid: { color: "rgba(255,255,255,0.05)" },
      },
    },
  }), []);

  const donutData = useMemo(() => ({
    labels: ["Прибыльные", "Убыточные"],
    datasets: [
      {
        data: metrics ? [metrics.wins, metrics.losses] : [0, 0],
        backgroundColor: [COLOR_GREEN, COLOR_RED],
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
        backgroundColor: "rgba(26, 31, 53, 0.95)",
        borderColor: "rgba(96, 165, 250, 0.25)",
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
      {/* ===== HEADER — тот же, что на главной и в обратной связи ===== */}
      <header className="stats-topbar">
        <div className="stats-topbar-left">
          <Link href="/home" className="stats-brand">
            <Zap size={28} />
            <span>CryptoBot</span>
          </Link>
          <nav className="stats-nav">
            <Link href="/home" className="stats-nav-item">Главная</Link>
            <Link href="/stats" className="stats-nav-item active">Статистика</Link>
            <Link href="/feedback" className="stats-nav-item">Обратная связь</Link>
            <Link href="/guides" className="stats-nav-item">Обучение</Link>
          </nav>
        </div>
        <div className="stats-topbar-right">
          <div className={`stats-balance ${getBalanceStatus(serviceBalance)}`}>
            <CreditCard size={16} />
            <span>{serviceBalance.toLocaleString('ru-RU')} ₽</span>
          </div>
          <Link href="/settings">
            <button className="stats-icon-btn">
              <Settings size={20} />
            </button>
          </Link>
        </div>
      </header>

      {/* ===== SCROLL AREA ===== */}
      <div className="stats-scroll">
        <main className="stats-main">
          {/* Заголовок вью + период */}
          <section className="stats-hero">
            <div>
              <h1>{selectedBot ? selectedBot.pair : "Все боты"}</h1>
              <p className="stats-hero-sub">
                {selectedBot
                  ? `x${selectedBot.leverage} · ${selectedBot.direction} · ${selectedBot.strategy_preset} · ${
                      selectedBot.status === "running" ? "Работает" : "Остановлен"
                    }`
                  : "Общая статистика портфеля"}
              </p>
            </div>
            <div className="stats-period">
              {(["1D", "1W", "1M"] as Period[]).map((p) => (
                <button
                  key={p}
                  className={`stats-period-tab ${period === p ? "active" : ""}`}
                  onClick={() => setPeriod(p)}
                >
                  {PERIOD_LABEL[p]}
                </button>
              ))}
            </div>
          </section>

          <div className="stats-layout">
            {/* ===== SIDEBAR ===== */}
            <aside className="stats-sidebar">
              <div className="sb-header">
                <div className="sb-section-label">Портфель</div>
                <button
                  className={`sb-all-btn ${view === "all" ? "active" : ""}`}
                  onClick={() => setView("all")}
                >
                  <LayoutGrid size={16} />
                  Все боты
                </button>
              </div>

              <div className="sb-bots">
                <div className="sb-section-label">
                  Боты ({sidebarBots.length})
                </div>
                {sidebarBots.length > 0 ? (
                  sidebarBots.map((b) => (
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
                      <div className={`bot-row-pnl ${b.profit >= 0 ? "text-green" : "text-red"}`}>
                        {formatUsdt(b.profit)}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="sb-empty">Ботов пока нет</div>
                )}
              </div>

              <div className="sb-footer">
                <div className="sb-footer-row">
                  <div className="sb-status-dot" />
                  {/* «неактивных», а не «остановленных»: сюда же попадают боты в статусах
                      created, starting и error */}
                  {runningCount} активных · {stoppedCount} неактивн
                  {stoppedCount === 1 ? "ый" : "ых"}
                </div>
              </div>
            </aside>

            {/* ===== CONTENT ===== */}
            <div className="stats-content">
              {/* Loading */}
              {loading && (
                <div className="stats-state">
                  <span className="stats-spin"><Loader2 size={20} /></span>
                  Загружаем статистику...
                </div>
              )}

              {/* Error */}
              {!loading && error && (
                <div className="stats-state error">
                  <AlertTriangle size={20} />
                  <span>{error}</span>
                  <button className="stats-retry-btn" onClick={fetchData}>Повторить</button>
                </div>
              )}

              {/* Content */}
              {!loading && !error && metrics && (
                <>
                  {/* Metrics */}
                  <div className="metrics-row">
                    <div className="metric-card">
                      <div className="metric-head">
                        <span className={`metric-icon ${metrics.profit >= 0 ? "green" : "red"}`}>
                          {metrics.profit >= 0 ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
                        </span>
                        <span className="metric-label">Общий P&L</span>
                      </div>
                      <div className={`metric-value ${pnlClass}`}>
                        {formatUsdt(metrics.profit)}
                      </div>
                      <div className="metric-sub">За выбранный период</div>
                    </div>

                    <div className="metric-card">
                      <div className="metric-head">
                        <span className="metric-icon blue">
                          <Target size={18} />
                        </span>
                        <span className="metric-label">Winrate</span>
                      </div>
                      <div className="metric-value text-white">{metrics.winrate}%</div>
                      <div className="metric-bar">
                        <div
                          className="metric-bar-fill"
                          style={{ width: `${metrics.winrate}%` }}
                        />
                      </div>
                    </div>

                    <div className="metric-card">
                      <div className="metric-head">
                        <span className="metric-icon blue">
                          <Activity size={18} />
                        </span>
                        <span className="metric-label">Всего сделок</span>
                      </div>
                      <div className="metric-value text-blue">{metrics.trades}</div>
                      <div className="metric-sub">
                        {metrics.wins} прибыль · {metrics.losses} убыток
                      </div>
                    </div>

                    <div className="metric-card">
                      <div className="metric-head">
                        <span className="metric-icon amber">
                          <ArrowDownRight size={18} />
                        </span>
                        <span className="metric-label">Макс. просадка</span>
                      </div>
                      <div className={`metric-value ${ddClass}`}>
                        {metrics.drawdown !== 0 ? `${metrics.drawdown.toFixed(1)}%` : "—"}
                      </div>
                      <div className="metric-sub">За выбранный период</div>
                    </div>
                  </div>

                  {/* Charts */}
                  <div className="charts-row">
                    <div className="stats-card">
                      <div className="stats-card-head">
                        <span className="card-label">P&L по времени</span>
                        <span
                          className="card-note"
                          style={{ color: trendColor, fontWeight: 700 }}
                        >
                          {lastValue >= 0 ? "+" : "-"}${Math.abs(lastValue).toFixed(2)} за период
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
                      <div className="stats-card-head">
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
                            <span className="legend-square" style={{ background: COLOR_GREEN }} />
                            <span className="legend-label">Прибыльные</span>
                            <span className="legend-value text-green">{metrics.wins}</span>
                          </div>
                          <div className="donut-legend-row">
                            <span className="legend-square" style={{ background: COLOR_RED }} />
                            <span className="legend-label">Убыточные</span>
                            <span className="legend-value text-red">{metrics.losses}</span>
                          </div>
                          <div className="donut-divider">
                            <span className="donut-divider-label">Winrate</span>
                            <span className="donut-divider-value">{metrics.winrate}%</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Trades table */}
                  <div className="stats-card">
                    <div className="stats-card-head">
                      <span className="card-label">Последние сделки</span>
                      <span className="card-note">{trades.length} сделок</span>
                    </div>
                    {trades.length > 0 ? (
                      <div className="table-scroll">
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
                                <td className="td-pair">{t.pair}</td>
                                <td>
                                  <span className={`dir-badge ${t.direction === "long" ? "long" : "short"}`}>
                                    {t.direction === "long" ? "Long" : "Short"}
                                  </span>
                                </td>
                                <td>{t.open_rate.toFixed(4)}</td>
                                <td>{t.close_rate != null ? t.close_rate.toFixed(4) : "—"}</td>
                                <td
                                  className={(t.profit_usdt ?? 0) >= 0 ? "text-green" : "text-red"}
                                  style={{ fontWeight: 700 }}
                                >
                                  {t.profit_usdt != null ? formatUsdt(t.profit_usdt) : "—"}
                                </td>
                                <td className={(t.profit_pct ?? 0) >= 0 ? "text-green" : "text-red"}>
                                  {t.profit_pct != null ? formatPnl(t.profit_pct) : "—"}
                                </td>
                                <td>{formatDuration(t.open_time, t.close_time)}</td>
                                <td className="td-muted">{formatDate(t.close_time)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="empty-trades">Сделок пока нет</div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

export default StatsPage;
