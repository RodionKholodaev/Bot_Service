'use client';
import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  Zap,
  Settings,
  CreditCard,
  ArrowLeft,
  ChevronRight,
  Wallet,
  Coins,
  Target,
  Shield,
  Activity,
  BarChart3,
  FlaskConical,
  Key,
  TrendingUp,
  TrendingDown,
  ArrowLeftRight,
  AlertTriangle,
  Loader2,
  Info,
} from 'lucide-react';
import { apiFetch } from '@/lib/api';
import type { BotPublic, FilterRule } from '@/lib/types';
import './bot-settings.css';

// Ключ отдаётся эндпоинтом /api-keys без секретов — нужен только чтобы
// показать имя ключа вместо голого api_key_id.
interface ApiKeyListItem {
  id: number;
  name: string;
  exchange: string;
}

// ===== Словари для человекочитаемых подписей =====
const STATUS_LABEL: Record<string, string> = {
  created: 'Создан',
  starting: 'Запускается',
  running: 'Работает',
  stopped: 'Остановлен',
  error: 'Ошибка',
};

const DIRECTION_LABEL: Record<string, string> = {
  long: 'Лонг (в рост)',
  short: 'Шорт (в падение)',
  both: 'Лонг и шорт',
};

const PRESET_LABEL: Record<string, string> = {
  conservative: 'Консервативный',
  moderate: 'Умеренный',
  aggressive: 'Агрессивный',
  custom: 'Пользовательская',
};

const PRESET_HINT: Record<string, string> = {
  conservative: 'Минимальный риск, небольшая прибыль',
  moderate: 'Баланс риска и прибыли',
  aggressive: 'Высокий риск, максимальная прибыль',
  custom: 'Условия входа заданы вручную',
};

const INDICATOR_LABEL: Record<string, string> = {
  rsi: 'RSI',
  cci: 'CCI',
};

const CONDITION_SIGN: Record<string, string> = {
  less: '<',
  greater: '>',
  less_equal: '≤',
  greater_equal: '≥',
};

const CONDITION_TEXT: Record<string, string> = {
  less: 'меньше',
  greater: 'больше',
  less_equal: 'меньше или равен',
  greater_equal: 'больше или равен',
};

const EXCHANGE_LABEL: Record<string, string> = {
  bybit: 'Bybit',
  binance: 'Binance',
};

// ===== Helpers =====

// "XRP/USDT:USDT" — фьючерсный формат freqtrade. Пользователь вводил "XRP/USDT".
const displayPair = (pair: string): string => pair.split(':')[0];

// take_profit хранится как minimal_roi: {"0": 0.04} → 4%
const takeProfitPercent = (roi: Record<string, number>): number | null => {
  const first = roi?.['0'] ?? Object.values(roi ?? {})[0];
  return typeof first === 'number' ? first * 100 : null;
};

// stop_loss хранится отрицательным; -0.99 означает «выключен» (см. bot_service)
const STOP_LOSS_DISABLED = -0.99;
const stopLossPercent = (sl: number): number | null =>
  sl <= STOP_LOSS_DISABLED ? null : Math.abs(sl) * 100;

const formatUsd = (v: number): string =>
  `$${v.toLocaleString('ru-RU', { maximumFractionDigits: 2 })}`;

const formatDateTime = (iso: string): string => {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return `${d.getDate().toString().padStart(2, '0')}.${(d.getMonth() + 1)
    .toString()
    .padStart(2, '0')}.${d.getFullYear()} ${d
    .getHours()
    .toString()
    .padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
};

// тот же светофор баланса, что на главной, в статистике и в обратной связи
const getBalanceStatus = (balance: number): string => {
  if (balance < 100) return 'critical';
  if (balance < 1000) return 'low';
  return 'good';
};

// ===== Мелкие презентационные блоки =====

const ParamRow = ({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  accent?: 'green' | 'red' | 'blue' | 'amber' | 'muted';
}) => (
  <div className="bs-row">
    <div className="bs-row-label">
      {label}
      {hint && <span className="bs-row-hint">{hint}</span>}
    </div>
    <div className={`bs-row-value ${accent ? `bs-${accent}` : ''}`}>
      {value}
    </div>
  </div>
);

const Card = ({
  icon,
  tone,
  title,
  subtitle,
  className = '',
  children,
}: {
  icon: React.ReactNode;
  tone: 'green' | 'red' | 'blue' | 'amber' | 'violet';
  title: string;
  subtitle?: string;
  className?: string;
  children: React.ReactNode;
}) => (
  <section className={`bs-card ${className}`.trim()}>
    <div className="bs-card-head">
      <div className={`bs-card-icon ${tone}`}>{icon}</div>
      <div>
        <h2>{title}</h2>
        {subtitle && <p className="bs-card-sub">{subtitle}</p>}
      </div>
    </div>
    <div className="bs-card-body">{children}</div>
  </section>
);

// Одно условие входа: «RSI · 5m  <  55»
const FilterChip = ({ rule }: { rule: FilterRule }) => (
  <div className="bs-filter">
    <span className="bs-filter-ind">
      {INDICATOR_LABEL[rule.indicator] ?? rule.indicator.toUpperCase()}
    </span>
    <span className="bs-filter-tf">{rule.timeframe}</span>
    <span className="bs-filter-cond" title={CONDITION_TEXT[rule.condition]}>
      {CONDITION_SIGN[rule.condition] ?? rule.condition}
    </span>
    <span className="bs-filter-val">{rule.value}</span>
  </div>
);

// ===== Component =====
const BotSettingsPage: React.FC = () => {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const botId = params?.id;

  const [bot, setBot] = useState<BotPublic | null>(null);
  const [apiKey, setApiKey] = useState<ApiKeyListItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [serviceBalance, setServiceBalance] = useState<number>(0);

  // проверка того что пользователь имеет JWT
  useEffect(() => {
    if (!localStorage.getItem('access_token')) {
      router.replace('/auth');
    }
  }, [router]);

  const load = useCallback(async () => {
    if (!botId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetch<BotPublic>(`/bots/${botId}`);
      setBot(data);
      // Имя ключа подтягиваем отдельно: в BotPublic лежит только api_key_id
      if (data.api_key_id != null) {
        try {
          const keys = await apiFetch<ApiKeyListItem[]>('/api-keys');
          setApiKey(keys.find((k) => k.id === data.api_key_id) ?? null);
        } catch {
          // ключ мог быть удалён — покажем id, страницу из-за этого не ломаем
          setApiKey(null);
        }
      }
    } catch (e) {
      console.error('Не удалось загрузить бота:', e);
      setError('Не удалось загрузить параметры бота');
    } finally {
      setLoading(false);
    }
  }, [botId]);

  useEffect(() => {
    if (!localStorage.getItem('access_token')) return;
    // Загрузка при монтировании: setState происходит уже после await,
    // каскадного ререндера нет — правило этого не различает.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load();
  }, [load]);

  useEffect(() => {
    if (!localStorage.getItem('access_token')) return;
    apiFetch<{ service_balance: number }>('/users/me/balance')
      .then((d) => setServiceBalance(d.service_balance))
      .catch((e) => console.error('Не удалось загрузить баланс:', e));
  }, []);

  const topbar = (
    <header className="bs-topbar">
      <div className="bs-topbar-left">
        <Link href="/home" className="bs-brand">
          <Zap size={28} />
          <span>CryptoBot</span>
        </Link>
        <nav className="bs-nav">
          <Link href="/home" className="bs-nav-item active">
            Главная
          </Link>
          <Link href="/stats" className="bs-nav-item">
            Статистика
          </Link>
          <Link href="/feedback" className="bs-nav-item">
            Обратная связь
          </Link>
          <Link href="/guides" className="bs-nav-item">
            Обучение
          </Link>
        </nav>
      </div>
      <div className="bs-topbar-right">
        <div className={`bs-balance ${getBalanceStatus(serviceBalance)}`}>
          <CreditCard size={16} />
          <span>{serviceBalance.toLocaleString('ru-RU')} ₽</span>
        </div>
        <Link href="/settings">
          <button className="bs-icon-btn">
            <Settings size={20} />
          </button>
        </Link>
      </div>
    </header>
  );

  if (loading || error || !bot) {
    return (
      <div className="bs-page">
        {topbar}
        <div className="bs-scroll">
          <main className="bs-main">
            {loading ? (
              <div className="bs-state">
                <Loader2 size={20} className="bs-spin" />
                <span>Загружаем параметры бота...</span>
              </div>
            ) : (
              <div className="bs-state error">
                <AlertTriangle size={20} />
                <span>{error ?? 'Бот не найден'}</span>
                <button className="bs-retry-btn" onClick={load}>
                  Повторить
                </button>
              </div>
            )}
          </main>
        </div>
      </div>
    );
  }

  const tp = takeProfitPercent(bot.take_profit);
  const sl = stopLossPercent(bot.stop_loss);
  const ratioPercent = bot.tradable_balance_ratio * 100;
  const perTrade = bot.stake_amount * bot.tradable_balance_ratio;
  const perTradeLeveraged = perTrade * bot.leverage;
  const isLong = bot.direction === 'long';
  const isShort = bot.direction === 'short';
  const longFilters = bot.entry_filters_long ?? [];
  const shortFilters = bot.entry_filters_short ?? [];

  return (
    <div className="bs-page">
      {topbar}

      <div className="bs-scroll">
        <main className="bs-main">
          {/* Хлебные крошки */}
          <div className="bs-crumbs">
            <Link href="/home">Главная</Link>
            <ChevronRight size={14} />
            <span>{bot.name}</span>
          </div>

          {/* ===== HERO ===== */}
          <section className="bs-hero">
            <div className="bs-hero-left">
              <div className="bs-hero-title">
                <h1>{bot.name}</h1>
                {bot.dry_run && (
                  <span
                    className="bs-badge demo"
                    title="Демо-режим: реальные сделки не совершаются"
                  >
                    <FlaskConical size={12} />
                    DEMO
                  </span>
                )}
                <span className={`bs-badge status ${bot.status}`}>
                  <span className="bs-dot" />
                  {STATUS_LABEL[bot.status] ?? bot.status}
                </span>
              </div>
              <p className="bs-hero-sub">
                {displayPair(bot.pair)} · x{bot.leverage} ·{' '}
                {DIRECTION_LABEL[bot.direction] ?? bot.direction} · создан{' '}
                {formatDateTime(bot.created_at)}
              </p>
            </div>
            <div className="bs-hero-actions">
              <Link href="/home" className="bs-btn-ghost">
                <ArrowLeft size={17} />К ботам
              </Link>
              <Link href="/stats" className="bs-btn-primary">
                <BarChart3 size={17} />
                Статистика
              </Link>
            </div>
          </section>

          {bot.status === 'error' && bot.error_message && (
            <div className="bs-alert">
              <AlertTriangle size={18} />
              <div className="bs-alert-body">
                <span className="bs-alert-title">Бот остановлен с ошибкой</span>
                {/* Текст приходит из докера/биржи «как есть» и бывает
                    длинным — прячем его в скроллящийся блок, чтобы он не
                    растягивал страницу. */}
                <code className="bs-alert-text">{bot.error_message}</code>
              </div>
            </div>
          )}

          {/* ===== ПАРАМЕТРЫ ===== */}
          <div className="bs-grid">
            {/* 1. Биржа, ключ, депозит */}
            <Card
              icon={<Wallet size={20} />}
              tone="blue"
              title="Биржа и депозит"
              subtitle="Шаг 1 при создании"
            >
              <ParamRow
                label="Режим торговли"
                value={bot.dry_run ? 'Демо (симуляция)' : 'Боевой'}
                accent={bot.dry_run ? 'amber' : 'green'}
              />
              <ParamRow
                label="API-ключ"
                value={
                  bot.dry_run ? (
                    <span className="bs-muted">Не нужен в демо-режиме</span>
                  ) : apiKey ? (
                    <span className="bs-key">
                      <Key size={14} />
                      {apiKey.name}
                    </span>
                  ) : bot.api_key_id != null ? (
                    <span className="bs-muted">Ключ #{bot.api_key_id}</span>
                  ) : (
                    <span className="bs-muted">Не выбран</span>
                  )
                }
              />
              <ParamRow
                label="Биржа"
                value={
                  apiKey
                    ? (EXCHANGE_LABEL[apiKey.exchange] ?? apiKey.exchange)
                    : 'Bybit'
                }
              />
              <ParamRow
                label="Депозит бота"
                value={formatUsd(bot.stake_amount)}
                hint="сколько USDT выделено боту"
              />
              <ParamRow
                label="Доля на сделку"
                value={`${ratioPercent.toFixed(ratioPercent % 1 === 0 ? 0 : 1)} %`}
                hint="часть депозита в одной позиции"
              />
              <ParamRow
                label="Сумма одной сделки"
                value={formatUsd(perTrade)}
                accent="blue"
              />
            </Card>

            {/* 2. Пара и плечо */}
            <Card
              icon={<Coins size={20} />}
              tone="violet"
              title="Пара и плечо"
              subtitle="Шаг 2 при создании"
            >
              <ParamRow
                label="Торговая пара"
                value={displayPair(bot.pair)}
                hint={bot.pair}
              />
              <ParamRow
                label="Кредитное плечо"
                value={`x${bot.leverage}`}
                accent={bot.leverage > 10 ? 'amber' : undefined}
              />
              <ParamRow
                label="Направление"
                value={
                  <span className="bs-direction">
                    {isLong ? (
                      <TrendingUp size={15} />
                    ) : isShort ? (
                      <TrendingDown size={15} />
                    ) : (
                      <ArrowLeftRight size={15} />
                    )}
                    {DIRECTION_LABEL[bot.direction] ?? bot.direction}
                  </span>
                }
                accent={isLong ? 'green' : isShort ? 'red' : 'blue'}
              />
              <ParamRow
                label="Объём позиции с плечом"
                value={formatUsd(perTradeLeveraged)}
                hint="сумма сделки × плечо"
              />
              {/* Из чего состоит позиция: свои деньги против заёмных у биржи */}
              <div className="bs-scale">
                <div className="bs-scale-bar">
                  <div
                    className="bs-scale-seg own"
                    style={{ width: `${100 / bot.leverage}%` }}
                  />
                  <div className="bs-scale-seg borrowed" />
                </div>
                <div className="bs-scale-legend">
                  <span className="bs-blue">свои {formatUsd(perTrade)}</span>
                  <span className="bs-scale-entry plain">x{bot.leverage}</span>
                  <span className="bs-muted">
                    заёмные {formatUsd(perTradeLeveraged - perTrade)}
                  </span>
                </div>
              </div>
            </Card>

            {/* 3. Выход из сделки */}
            <Card
              icon={<Target size={20} />}
              tone="green"
              title="Выход из сделки"
              subtitle="Шаг 4 при создании"
            >
              <ParamRow
                label="Take Profit"
                value={tp !== null ? `+${tp.toFixed(2)} %` : '—'}
                hint="фиксация прибыли"
                accent="green"
              />
              <ParamRow
                label="Stop Loss"
                value={
                  sl !== null ? (
                    `−${sl.toFixed(2)} %`
                  ) : (
                    <span className="bs-muted">Отключён</span>
                  )
                }
                hint="ограничение убытка"
                accent={sl !== null ? 'red' : undefined}
              />
              <ParamRow
                label="Соотношение прибыль / риск"
                value={
                  tp !== null && sl !== null ? (
                    `${(tp / sl).toFixed(2)} : 1`
                  ) : (
                    <span className="bs-muted">—</span>
                  )
                }
                hint="во сколько раз цель больше допустимого убытка"
              />
              <div className="bs-scale">
                <div className="bs-scale-bar">
                  {sl !== null && (
                    <div
                      className="bs-scale-seg loss"
                      style={{ width: `${(sl / (sl + (tp ?? 0))) * 100}%` }}
                    />
                  )}
                  <div className="bs-scale-seg profit" />
                </div>
                <div className="bs-scale-legend">
                  <span className="bs-red">
                    {sl !== null ? `−${sl.toFixed(2)} %` : 'без ограничения'}
                  </span>
                  <span className="bs-scale-entry">вход</span>
                  <span className="bs-green">
                    {tp !== null ? `+${tp.toFixed(2)} %` : '—'}
                  </span>
                </div>
              </div>
            </Card>

            {/* 4. Служебное */}
            <Card
              className="bs-card-state"
              icon={<Activity size={20} />}
              tone="amber"
              title="Состояние бота"
              subtitle="Заполняет сервис"
            >
              <ParamRow
                label="Статус"
                value={STATUS_LABEL[bot.status] ?? bot.status}
                accent={
                  bot.status === 'running'
                    ? 'green'
                    : bot.status === 'error'
                      ? 'red'
                      : 'muted'
                }
              />
              <ParamRow
                label="Накопленная прибыль"
                value={`${(bot.total_profit ?? 0) >= 0 ? '+' : '−'}$${Math.abs(
                  bot.total_profit ?? 0,
                ).toFixed(2)}`}
                accent={(bot.total_profit ?? 0) >= 0 ? 'green' : 'red'}
              />
              <ParamRow label="Создан" value={formatDateTime(bot.created_at)} />
            </Card>

            {/* 5. Стратегия — справа от «Состояния бота», под шагами 2 и 4 */}
            <Card
              className="bs-card-strategy"
              icon={<Shield size={20} />}
              tone="blue"
              title="Стратегия входа"
              subtitle="Шаг 3 при создании"
            >
              <ParamRow
                label="Набор условий"
                value={PRESET_LABEL[bot.strategy_preset] ?? bot.strategy_preset}
                hint={PRESET_HINT[bot.strategy_preset]}
              />

              <div className="bs-note">
                <Info size={15} />
                <span>
                  Бот открывает сделку, только когда выполнены{' '}
                  <strong>все</strong> условия одновременно.
                </span>
              </div>

              {longFilters.length > 0 && (
                <div className="bs-filters-block">
                  <div className="bs-filters-title green">
                    <TrendingUp size={15} />
                    Вход в лонг · {longFilters.length}{' '}
                    {longFilters.length === 1 ? 'условие' : 'условий'}
                  </div>
                  <div className="bs-filters">
                    {longFilters.map((rule, i) => (
                      <FilterChip key={`long-${i}`} rule={rule} />
                    ))}
                  </div>
                </div>
              )}

              {shortFilters.length > 0 && (
                <div className="bs-filters-block">
                  <div className="bs-filters-title red">
                    <TrendingDown size={15} />
                    Вход в шорт · {shortFilters.length}{' '}
                    {shortFilters.length === 1 ? 'условие' : 'условий'}
                  </div>
                  <div className="bs-filters">
                    {shortFilters.map((rule, i) => (
                      <FilterChip key={`short-${i}`} rule={rule} />
                    ))}
                  </div>
                </div>
              )}

              {longFilters.length === 0 && shortFilters.length === 0 && (
                <div className="bs-empty">Условия входа не заданы</div>
              )}
            </Card>
          </div>

          <p className="bs-footnote">
            Параметры бота нельзя изменить после создания. Чтобы торговать по
            другим настройкам, остановите этого бота и{' '}
            <Link href="/bot-creation">создайте нового</Link>.
          </p>
        </main>
      </div>
    </div>
  );
};

export default BotSettingsPage;
