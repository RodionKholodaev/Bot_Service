'use client';
import React, {
  useEffect,
  useMemo,
  useRef,
  useState,
  useCallback,
} from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { TooltipItem } from 'chart.js';
import { BrandMark } from '@/app/components/BrandMark';
import {
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
} from 'lucide-react';
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
} from 'chart.js';
import { Line, Doughnut } from 'react-chartjs-2';
import './stats.css';
import { apiFetch } from '@/lib/api';
import { presetLabel } from '@/lib/constants';
import { SiteFooter } from '@/app/components/SiteFooter';
import { formatSignedUsd, moneySign } from '@/lib/money';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Filler,
  Tooltip,
  Legend,
);

// ===== Types (зеркалят бэкенд schemas/stats.py) =====
type Period = '1D' | '1W' | '1M';
// Какие боты попадают в портфель. Значения зеркалят BOT_TYPE_MAP в routers/stats.py
type BotType = 'all' | 'real' | 'dry';
type ViewKey = 'all' | string;

interface PnlPoint {
  ts: string; // ISO-время закрытия сделки (UTC), формат выбираем здесь
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
  dry_run: boolean; // симуляция — по этому полю фильтруется список
  profit: number; // за выбранный период
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
  profit: number; // за выбранный период, а не за всё время
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
  profit: number; // за выбранный период
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
const PERIOD_LABEL: Record<Period, string> = {
  '1D': '1Д',
  '1W': '1Н',
  '1M': '1М',
};

const BOT_TYPE_LABEL: Record<BotType, string> = {
  all: 'Все',
  real: 'Боевые',
  dry: 'Dry-run',
};

// Подходит ли бот под выбранный фильтр — тем же правилом, что и на бэкенде
const matchesBotType = (bot: BotSummary, type: BotType): boolean =>
  type === 'all' || (type === 'dry' ? bot.dry_run : !bot.dry_run);

// Палитра графиков. Canvas не читает CSS-переменные, поэтому значения
// повторяют токены из app/globals.css — менять надо оба места.
const COLOR_GREEN = '#34d399'; // --success
const COLOR_RED = '#f87171'; // --danger
const COLOR_PAGE = '#111626'; // --bg-page
const COLOR_TOOLTIP_BG = '#1a1f35'; // --bg-elevated
const COLOR_TOOLTIP_BORDER = 'rgba(96, 165, 250, 0.3)'; // --accent-soft 30%
const COLOR_TEXT = '#e4e7f0'; // --text
const COLOR_TEXT_SECONDARY = '#9ca3af'; // --text-secondary
const COLOR_TEXT_MUTED = '#6b7280'; // --text-muted
const COLOR_GRID = 'rgba(255, 255, 255, 0.06)'; // --border-subtle

const formatPnl = (v: number): string => {
  const s = moneySign(v);
  return `${s > 0 ? '+' : s < 0 ? '-' : ''}${Math.abs(v).toFixed(2)}%`;
};
// Знак ставим перед $, минус — обязательно: без него убыток выглядел бы как прибыль
const formatUsdt = formatSignedUsd;
// Цвет только у суммы со знаком: ноль и пустое значение остаются цветом текста
const pnlTone = (v: number | null | undefined): string => {
  if (v == null) return '';
  const s = moneySign(v);
  return s > 0 ? 'text-green' : s < 0 ? 'text-red' : '';
};

const formatDuration = (open: string, close: string | null): string => {
  if (!close) return '—';
  const diff = (new Date(close).getTime() - new Date(open).getTime()) / 1000;
  const h = Math.floor(diff / 3600);
  const m = Math.floor((diff % 3600) / 60);
  return h > 0 ? `${h}ч ${m}м` : `${m}м`;
};

const formatDate = (iso: string | null): string => {
  if (!iso) return '—';
  const d = new Date(iso);
  return `${d.getDate().toString().padStart(2, '0')}.${(d.getMonth() + 1)
    .toString()
    .padStart(2, '0')} ${d.getHours().toString().padStart(2, '0')}:${d
    .getMinutes()
    .toString()
    .padStart(2, '0')}`;
};

// тот же светофор баланса, что на главной и в обратной связи
const getBalanceStatus = (balance: number): string => {
  if (balance < 100) return 'critical';
  if (balance < 1000) return 'low';
  return 'good';
};

// ===== Component =====
const StatsPage: React.FC = () => {
  const router = useRouter();
  const [view, setView] = useState<ViewKey>('all');
  const [period, setPeriod] = useState<Period>('1W');
  const [botType, setBotType] = useState<BotType>('all');
  const [portfolio, setPortfolio] = useState<PortfolioStats | null>(null);
  const [botData, setBotData] = useState<BotStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const chartRef = useRef<ChartJS<'line'> | null>(null);
  const [serviceBalance, setServiceBalance] = useState<number>(0);

  // проверка того что пользователь имеет JWT
  useEffect(() => {
    if (!localStorage.getItem('access_token')) {
      router.replace('/auth');
    }
  }, [router]);

  // Баланс нужен только для индикатора в шапке — той же, что на /home и /feedback
  const fetchBalance = useCallback(async () => {
    try {
      const data = await apiFetch<{ service_balance: number }>(
        '/users/me/balance',
      );
      setServiceBalance(data.service_balance);
    } catch (e) {
      console.error('Не удалось загрузить баланс:', e);
    }
  }, []);

  useEffect(() => {
    if (!localStorage.getItem('access_token')) return;
    // Обычная загрузка данных при монтировании: setState происходит уже после
    // await внутри fetchBalance, каскадного ререндера нет. Правило этого
    // не различает и ругается на любой вызов функции с setState внутри.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchBalance();
  }, [fetchBalance]);

  // Загрузка данных при смене вью или периода
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Портфель запрашиваем всегда: числа в сайдбаре считаются за выбранный период,
      // поэтому при смене периода они устаревают, даже когда открыт отдельный бот.
      const [pData, bData] = await Promise.all([
        apiFetch<PortfolioStats>(
          `/stats/portfolio?period=${period}&bot_type=${botType}`,
        ),
        view === 'all'
          ? Promise.resolve(null)
          : apiFetch<BotStats>(`/stats/bots/${view}?period=${period}`),
      ]);
      setPortfolio(pData);
      setBotData(bData);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Ошибка загрузки данных');
    } finally {
      setLoading(false);
    }
  }, [view, period, botType]);

  useEffect(() => {
    if (!localStorage.getItem('access_token')) return;
    // Перезагрузка при смене вью/периода — fetchData ставит state после await.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchData();
  }, [fetchData]);

  // ===== Текущие метрики =====
  const current: PortfolioStats | BotStats | null =
    view === 'all' ? portfolio : botData;

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

  const lastValue =
    chartSeries.length > 0 ? chartSeries[chartSeries.length - 1].value : 0;
  const trendColor = lastValue >= 0 ? COLOR_GREEN : COLOR_RED;

  // ===== Chart configs =====
  const lineData = useMemo(
    () => ({
      labels: chartSeries.map((p) => formatDate(p.ts)),
      datasets: [
        {
          data: chartSeries.map((p) => p.value),
          borderColor: trendColor,
          borderWidth: 2,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: trendColor,
          pointHoverBorderColor: COLOR_PAGE,
          pointHoverBorderWidth: 2,
          fill: true,
          backgroundColor: (ctx: { chart: ChartJS }) => {
            const c = ctx.chart.ctx;
            if (!c) return trendColor + '20';
            const g = c.createLinearGradient(0, 0, 0, 220);
            g.addColorStop(0, trendColor + '45');
            g.addColorStop(1, trendColor + '00');
            return g;
          },
          tension: 0.4,
        },
      ],
    }),
    [chartSeries, trendColor],
  );

  const lineOptions = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: COLOR_TOOLTIP_BG,
          borderColor: COLOR_TOOLTIP_BORDER,
          borderWidth: 1,
          padding: 10,
          titleColor: COLOR_TEXT_SECONDARY,
          bodyColor: COLOR_TEXT,
          callbacks: {
            label: (ctx: TooltipItem<'line'>) => {
              const y = ctx.parsed.y ?? 0;
              return `${formatUsdt(y)} USDT`;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: {
            color: COLOR_TEXT_MUTED,
            font: { size: 10 },
            maxTicksLimit: 8,
          },
          grid: { color: COLOR_GRID },
        },
        y: {
          ticks: {
            color: COLOR_TEXT_MUTED,
            font: { size: 10 },
            callback: (v: string | number) => formatSignedUsd(Number(v), 1),
          },
          grid: { color: COLOR_GRID },
        },
      },
    }),
    [],
  );

  const donutData = useMemo(
    () => ({
      labels: ['Прибыльные', 'Убыточные'],
      datasets: [
        {
          data: metrics ? [metrics.wins, metrics.losses] : [0, 0],
          backgroundColor: [COLOR_GREEN, COLOR_RED],
          borderWidth: 0,
          hoverOffset: 4,
        },
      ],
    }),
    [metrics],
  );

  const donutOptions = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      cutout: '72%',
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: COLOR_TOOLTIP_BG,
          borderColor: COLOR_TOOLTIP_BORDER,
          borderWidth: 1,
          padding: 10,
          titleColor: COLOR_TEXT_SECONDARY,
          bodyColor: COLOR_TEXT,
        },
      },
    }),
    [],
  );

  // Данные для сайдбара всегда из portfolio
  const sidebarBots = portfolio?.bots ?? [];

  // Смена фильтра по типу ботов. Выбранный бот может под новый фильтр не подходить —
  // тогда возвращаемся к портфелю: иначе на экране остался бы бот, которого нет
  // в сайдбаре, а его статистика продолжала бы грузиться отдельным запросом.
  const changeBotType = (type: BotType) => {
    setBotType(type);
    const selected = sidebarBots.find((b) => b.bot_id === view);
    if (selected && !matchesBotType(selected, type)) setView('all');
  };
  const runningCount = portfolio?.bots_running ?? 0;
  const stoppedCount = portfolio?.bots_stopped ?? 0;

  const selectedBot =
    view === 'all' ? null : sidebarBots.find((b) => b.bot_id === view);
  const pnlClass = pnlTone(metrics?.profit);

  return (
    <div className="stats-page">
      {/* ===== HEADER — тот же, что на главной и в обратной связи ===== */}
      <header className="stats-topbar">
        <div className="stats-topbar-left">
          <Link href="/home" className="stats-brand">
            <BrandMark size={28} />
            <span>Rudder</span>
          </Link>
          <nav className="stats-nav">
            <Link href="/home" className="stats-nav-item">
              Главная
            </Link>
            <Link href="/stats" className="stats-nav-item active">
              Статистика
            </Link>
            <Link href="/feedback" className="stats-nav-item">
              Обратная связь
            </Link>
            <Link href="/guides" className="stats-nav-item">
              Обучение
            </Link>
          </nav>
        </div>
        <div className="stats-topbar-right">
          <div className={`stats-balance ${getBalanceStatus(serviceBalance)}`}>
            <CreditCard size={16} />
            <span>{serviceBalance.toLocaleString('ru-RU')} ₽</span>
          </div>
          <Link href="/settings">
            <button className="stats-icon-btn" aria-label="Настройки">
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
              <h1>{selectedBot ? selectedBot.pair : 'Все боты'}</h1>
              {selectedBot ? (
                <div className="stats-hero-tags">
                  <span className="stats-hero-tag">
                    x{selectedBot.leverage}
                  </span>
                  <span className="stats-hero-tag">
                    {selectedBot.direction}
                  </span>
                  <span className="stats-hero-tag">
                    {presetLabel(selectedBot.strategy_preset)}
                  </span>
                  {selectedBot.dry_run && (
                    <span className="stats-hero-tag">Dry-run</span>
                  )}
                  <span className="stats-hero-tag">
                    {selectedBot.status === 'running'
                      ? 'Работает'
                      : 'Остановлен'}
                  </span>
                </div>
              ) : (
                <p className="stats-hero-sub">Общая статистика портфеля</p>
              )}
            </div>
            <div className="stats-hero-controls">
              <div className="stats-period">
                {(['1D', '1W', '1M'] as Period[]).map((p) => (
                  <button
                    key={p}
                    className={`stats-period-tab ${period === p ? 'active' : ''}`}
                    onClick={() => setPeriod(p)}
                  >
                    {PERIOD_LABEL[p]}
                  </button>
                ))}
              </div>
              {/* Фильтр по типу ботов: прибыль dry-run ненастоящая, и в одной сумме
                  с реальной она вводит в заблуждение */}
              <div className="stats-period stats-bot-type">
                {(['all', 'real', 'dry'] as BotType[]).map((t) => (
                  <button
                    key={t}
                    className={`stats-period-tab ${botType === t ? 'active' : ''}`}
                    onClick={() => changeBotType(t)}
                  >
                    {BOT_TYPE_LABEL[t]}
                  </button>
                ))}
              </div>
            </div>
          </section>

          <div className="stats-layout">
            {/* ===== SIDEBAR ===== */}
            <aside className="stats-sidebar">
              <div className="sb-header">
                <div className="sb-section-label">Портфель</div>
                <button
                  className={`sb-all-btn ${view === 'all' ? 'active' : ''}`}
                  onClick={() => setView('all')}
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
                      className={`bot-row ${view === b.bot_id ? 'active' : ''}`}
                      onClick={() => setView(b.bot_id)}
                    >
                      <div className="bot-row-info">
                        <div className="bot-row-name">
                          {b.pair}
                          {b.dry_run && (
                            <span className="bot-row-badge">Dry</span>
                          )}
                        </div>
                        <div className="bot-row-sub">
                          x{b.leverage}, {presetLabel(b.strategy_preset)}
                        </div>
                      </div>
                      <div className={`bot-row-pnl ${pnlTone(b.profit)}`}>
                        {formatUsdt(b.profit)}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="sb-empty">
                    {botType === 'all'
                      ? 'Ботов пока нет'
                      : `Нет ботов: ${BOT_TYPE_LABEL[botType].toLowerCase()}`}
                  </div>
                )}
              </div>

              <div className="sb-footer">
                <div className="sb-footer-row">
                  {/* «неактивных», а не «остановленных»: сюда же попадают боты в статусах
                      created, starting и error */}
                  {runningCount} активных, {stoppedCount} неактивн
                  {stoppedCount === 1 ? 'ый' : 'ых'}
                </div>
              </div>
            </aside>

            {/* ===== CONTENT ===== */}
            <div className="stats-content">
              {/* Loading */}
              {loading && (
                <div className="stats-state">
                  <span className="stats-spin">
                    <Loader2 size={20} />
                  </span>
                  Загружаем статистику...
                </div>
              )}

              {/* Error */}
              {!loading && error && (
                <div className="stats-state error">
                  <AlertTriangle size={20} />
                  <span>{error}</span>
                  <button className="stats-retry-btn" onClick={fetchData}>
                    Повторить
                  </button>
                </div>
              )}

              {/* Content */}
              {!loading && !error && metrics && (
                <>
                  {/* Metrics */}
                  <div className="metrics-row">
                    <div className="metric-card">
                      <div className="metric-head">
                        <span className="metric-icon">
                          {metrics.profit >= 0 ? (
                            <TrendingUp size={18} />
                          ) : (
                            <TrendingDown size={18} />
                          )}
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
                        <span className="metric-icon">
                          <Target size={18} />
                        </span>
                        <span className="metric-label">Winrate</span>
                      </div>
                      <div className="metric-value">{metrics.winrate}%</div>
                      <div className="metric-bar">
                        <div
                          className="metric-bar-fill"
                          style={{
                            transform: `scaleX(${metrics.winrate / 100})`,
                          }}
                        />
                      </div>
                    </div>

                    <div className="metric-card">
                      <div className="metric-head">
                        <span className="metric-icon">
                          <Activity size={18} />
                        </span>
                        <span className="metric-label">Всего сделок</span>
                      </div>
                      <div className="metric-value">{metrics.trades}</div>
                      <div className="metric-sub">
                        Прибыльных {metrics.wins}, убыточных {metrics.losses}
                      </div>
                    </div>

                    <div className="metric-card">
                      <div className="metric-head">
                        <span className="metric-icon">
                          <ArrowDownRight size={18} />
                        </span>
                        <span className="metric-label">Макс. просадка</span>
                      </div>
                      <div className="metric-value">
                        {metrics.drawdown !== 0
                          ? `${metrics.drawdown.toFixed(1)}%`
                          : '—'}
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
                          className={`card-note ${pnlTone(lastValue)}`}
                          style={{ fontWeight: 700 }}
                        >
                          {formatUsdt(lastValue)} за период
                        </span>
                      </div>
                      <div className="chart-wrap">
                        {chartSeries.length > 0 ? (
                          <Line
                            ref={chartRef as React.RefObject<ChartJS<'line'>>}
                            data={lineData}
                            options={lineOptions}
                          />
                        ) : (
                          <div className="empty-trades">
                            Нет данных за период
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="stats-card">
                      <div className="stats-card-head">
                        <span className="card-label">Распределение сделок</span>
                        <span className="card-note">
                          Прибыльных {metrics.wins}, убыточных {metrics.losses}
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
                              style={{ background: COLOR_GREEN }}
                            />
                            <span className="legend-label">Прибыльные</span>
                            <span className="legend-value">{metrics.wins}</span>
                          </div>
                          <div className="donut-legend-row">
                            <span
                              className="legend-square"
                              style={{ background: COLOR_RED }}
                            />
                            <span className="legend-label">Убыточные</span>
                            <span className="legend-value">
                              {metrics.losses}
                            </span>
                          </div>
                          <div className="donut-divider">
                            <span className="donut-divider-label">Winrate</span>
                            <span className="donut-divider-value">
                              {metrics.winrate}%
                            </span>
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
                                  <span className="dir-badge">
                                    {t.direction === 'long' ? 'Long' : 'Short'}
                                  </span>
                                </td>
                                <td>{t.open_rate.toFixed(4)}</td>
                                <td>
                                  {t.close_rate != null
                                    ? t.close_rate.toFixed(4)
                                    : '—'}
                                </td>
                                <td
                                  className={pnlTone(t.profit_usdt)}
                                  style={{ fontWeight: 700 }}
                                >
                                  {t.profit_usdt != null
                                    ? formatUsdt(t.profit_usdt)
                                    : '—'}
                                </td>
                                <td className={pnlTone(t.profit_pct)}>
                                  {t.profit_pct != null
                                    ? formatPnl(t.profit_pct)
                                    : '—'}
                                </td>
                                <td>
                                  {formatDuration(t.open_time, t.close_time)}
                                </td>
                                <td className="td-muted">
                                  {formatDate(t.close_time)}
                                </td>
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
          <SiteFooter />
        </main>
      </div>
    </div>
  );
};

export default StatsPage;
