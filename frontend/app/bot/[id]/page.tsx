'use client';

/* Страница настроек одного бота: /bot/{id}.
 *
 * Открывается шестерёнкой и кнопкой «Подробнее» в карточке бота на главной —
 * до её появления обе ссылки вели в 404.
 *
 * Страница только показывает настройки: правки бэкенд пока не принимает (у
 * /bots нет PATCH, а стратегия и config.json пишутся один раз при создании и
 * старте, см. services/bot_service.py). Поэтому здесь нет режима
 * редактирования — только чтение, запуск/остановка и удаление.
 *
 * Все производные цифры (размер сделки, объём позиции, деньги на TP/SL,
 * ликвидация) считаются здесь из stake_amount / tradable_balance_ratio /
 * плеча — бэкенд их не отдаёт, а показывать проценты без денег бесполезно:
 * ровно эту арифметику пользователь и делает в уме, ошибаясь на плечо.
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { BrandMark } from '@/app/components/BrandMark';
import {
  AlertTriangle,
  ArrowLeft,
  BarChart3,
  Bot as BotIcon,
  ClipboardList,
  CreditCard,
  DollarSign,
  Info,
  KeyRound,
  Loader2,
  Pause,
  Play,
  Settings,
  Target,
  Trash2,
} from 'lucide-react';
import { apiFetch, ApiError } from '@/lib/api';
import {
  MIN_SERVICE_BALANCE_RUB,
  presetLabel,
  INDICATOR_META,
  indicatorLabel,
} from '@/lib/constants';
import type { BotPublic, FilterRule } from '@/lib/types';
import { SiteFooter } from '@/app/components/SiteFooter';
import './bot-detail.css';

// ── Типы ответов бэкенда, нужные только этой странице ─────

/** GET /stats/bots/{id} — берём из него счётчики сделок и winrate. */
interface BotStats {
  profit: number;
  trades_total: number;
  trades_win: number;
  trades_loss: number;
  winrate: number;
  avg_profit_pct: number | null;
  max_drawdown_pct: number | null;
}

/** GET /bots/{id}/open-trades */
interface OpenTrade {
  pair: string;
  direction: string;
  open_rate: number;
  amount: number;
  open_time: string;
}

/** GET /api-keys — нужен только name ключа, которым подписан бот. */
interface ApiKeyListItem {
  id: number;
  name: string;
  exchange: string;
}

// ── Подписи ───────────────────────────────────────────────

const STATUS_LABEL: Record<string, string> = {
  running: 'Работает',
  starting: 'Запускается',
  stopped: 'Остановлен',
  created: 'Создан',
  error: 'Ошибка',
};

const CONDITION_LABEL: Record<string, string> = {
  less: 'ниже',
  greater: 'выше',
  less_equal: 'ниже или равен',
  greater_equal: 'выше или равен',
};

// Комиссия тейкера Bybit — 0.055% с объёма за сделку, круг (вход + выход) даёт
// 0.11%. Значение зашито и помечено на странице как приблизительное: бэкенд
// реальную комиссию биржи наружу не отдаёт, а порядок величины пользователю
// нужен — на большом плече она съедает заметную часть take profit.
const TAKER_FEE_ROUND_PERCENT = 0.11;

const fmtMoney = (value: number) =>
  value.toLocaleString('ru-RU', { maximumFractionDigits: 2 });

const fmtDate = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? '—'
    : d.toLocaleDateString('ru-RU', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      });
};

const balanceClass = (balance: number | null) => {
  if (balance === null) return 'good';
  if (balance < MIN_SERVICE_BALANCE_RUB) return 'critical';
  if (balance < 1000) return 'low';
  return 'good';
};

export default function BotDetailPage() {
  const params = useParams<{ id: string }>();
  const botId = typeof params?.id === 'string' ? params.id : '';
  const router = useRouter();

  const [bot, setBot] = useState<BotPublic | null>(null);
  const [stats, setStats] = useState<BotStats | null>(null);
  const [openTrades, setOpenTrades] = useState<OpenTrade[] | null>(null);
  const [apiKeys, setApiKeys] = useState<ApiKeyListItem[]>([]);
  const [serviceBalance, setServiceBalance] = useState<number | null>(null);

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [showDelete, setShowDelete] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem('access_token')) {
      router.replace('/auth');
    }
  }, [router]);

  const fetchBot = useCallback(async () => {
    if (!botId) return;
    try {
      setLoadError(null);
      setBot(
        await apiFetch<BotPublic>(`/bots/${botId}`, { cache: 'no-store' }),
      );
    } catch (e) {
      // 404 — бот удалён или чужой; это не сбой загрузки, а отдельное состояние
      // страницы, из которого ведёт только ссылка назад.
      if (e instanceof ApiError && e.status === 404) {
        setNotFound(true);
      } else {
        const msg = e instanceof Error ? e.message : 'Неизвестная ошибка';
        setLoadError(`Не удалось загрузить бота: ${msg}`);
      }
    } finally {
      setLoading(false);
    }
  }, [botId]);

  // Второстепенные данные грузятся отдельно и молча: без счётчиков сделок или
  // имени ключа страница остаётся полезной, а падать целиком из-за них нельзя.
  const fetchSecondary = useCallback(async () => {
    if (!botId) return;
    const [statsRes, tradesRes, keysRes, balanceRes] = await Promise.allSettled(
      [
        apiFetch<BotStats>(`/stats/bots/${botId}?period=all`, {
          cache: 'no-store',
        }),
        apiFetch<OpenTrade[]>(`/bots/${botId}/open-trades`, {
          cache: 'no-store',
        }),
        // Путь с явным /api: apiFetch дописывает префикс только тем путям, что не
        // начинаются на «/api», а «/api-keys» под это условие попадает — и запрос
        // ушёл бы на несуществующий /api-keys самого Next. Остальные страницы
        // пишут его так же.
        apiFetch<ApiKeyListItem[]>('/api/api-keys', { cache: 'no-store' }),
        apiFetch<{ service_balance: number }>('/users/me/balance', {
          cache: 'no-store',
        }),
      ],
    );

    if (statsRes.status === 'fulfilled') setStats(statsRes.value);
    if (tradesRes.status === 'fulfilled') setOpenTrades(tradesRes.value);
    if (keysRes.status === 'fulfilled') setApiKeys(keysRes.value);
    if (balanceRes.status === 'fulfilled') {
      setServiceBalance(balanceRes.value.service_balance);
    }
  }, [botId]);

  useEffect(() => {
    if (!localStorage.getItem('access_token')) return;
    // Обычная загрузка при монтировании: setState происходит уже после await
    // внутри функций, каскадного ререндера нет. Правило этого не различает —
    // тот же disable стоит на главной.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchBot();
    fetchSecondary();
    // Статус меняется на бэкенде (polling_worker может остановить бота сам) —
    // держим страницу свежей тем же интервалом, что и список на главной.
    const interval = setInterval(fetchBot, 15000);
    return () => clearInterval(interval);
  }, [fetchBot, fetchSecondary]);

  // ── Производные величины ────────────────────────────────

  const derived = useMemo(() => {
    if (!bot) return null;

    const deposit = bot.stake_amount;
    const riskPercent = bot.tradable_balance_ratio * 100;
    const margin = deposit * bot.tradable_balance_ratio;
    const notional = margin * bot.leverage;

    const tp = bot.take_profit_percent;
    const sl = bot.stop_loss_percent;
    // stop_loss_percent === null означает и «стоп выключен», и «бот создан до
    // появления этих полей» — различить нельзя, поэтому текст нейтральный.
    const slEnabled = sl !== null;

    const filters: FilterRule[] =
      bot.direction === 'long'
        ? bot.entry_filters_long
        : bot.entry_filters_short;

    // Риск на глаз: доля депозита в сделке, умноженная на плечо, плюс надбавка
    // за выключенный стоп. Шкала грубая и нужна только чтобы отличить
    // «20% с плечом x1» от «100% с плечом x20».
    const riskScore = Math.min(
      100,
      Math.round((riskPercent * bot.leverage) / 2 + (slEnabled ? 0 : 15)),
    );
    const riskLabel =
      riskScore < 25
        ? 'Низкий'
        : riskScore < 55
          ? 'Умеренный'
          : riskScore < 80
            ? 'Высокий'
            : 'Очень высокий';
    const riskColor =
      riskScore < 25
        ? '#34d399'
        : riskScore < 55
          ? '#60a5fa'
          : riskScore < 80
            ? '#fbbf24'
            : '#f87171';

    return {
      deposit,
      riskPercent,
      margin,
      notional,
      tp,
      sl,
      slEnabled,
      filters,
      tpMoney: tp === null ? null : (notional * tp) / 100,
      slMoney: sl === null ? null : (notional * sl) / 100,
      // Проценты пользователя — движение цены; плечо переводит их в долю маржи.
      tpOfMargin: tp === null ? null : tp * bot.leverage,
      slOfMargin: sl === null ? null : sl * bot.leverage,
      feeOfMargin: TAKER_FEE_ROUND_PERCENT * bot.leverage,
      liquidationMove: 100 / bot.leverage,
      riskScore,
      riskLabel,
      riskColor,
    };
  }, [bot]);

  const apiKeyName = useMemo(() => {
    if (!bot) return '—';
    if (bot.dry_run) return '— (Dry Run)';
    if (bot.api_key_id === null) return 'Ключ удалён';
    const key = apiKeys.find((k) => k.id === bot.api_key_id);
    return key ? `${key.exchange} — ${key.name}` : `#${bot.api_key_id}`;
  }, [bot, apiKeys]);

  // ── Действия ────────────────────────────────────────────

  const isRunning = bot?.status === 'running';
  const isStarting = bot?.status === 'starting';
  const lowBalance =
    serviceBalance !== null && serviceBalance < MIN_SERVICE_BALANCE_RUB;
  // Остановить можно всегда; запустить боевого бота при низком балансе бэкенд
  // всё равно отобьёт 402-м (см. services/balance_guard.py) — гасим кнопку заранее.
  const startBlocked =
    !!bot && lowBalance && !bot.dry_run && !isRunning && !isStarting;

  const handleStartStop = async () => {
    if (!bot) return;
    const action = isRunning || isStarting ? 'stop' : 'start';
    setPending(true);
    setActionError(null);
    try {
      setBot(
        await apiFetch<BotPublic>(`/bots/${bot.id}/${action}`, {
          method: 'POST',
        }),
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Неизвестная ошибка';
      setActionError(msg);
      // Одна из причин отказа — что баланс ушёл ниже порога, пока страница была
      // открыта: перечитываем всё, чтобы показать причину, а не только текст ошибки.
      fetchBot();
      fetchSecondary();
    } finally {
      setPending(false);
    }
  };

  const handleDelete = async () => {
    if (!bot) return;
    setPending(true);
    try {
      await apiFetch(`/bots/${bot.id}`, { method: 'DELETE' });
      router.push('/home');
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Неизвестная ошибка';
      setActionError(`Не удалось удалить бота: ${msg}`);
      setPending(false);
      setShowDelete(false);
    }
  };

  // ── Разметка ────────────────────────────────────────────

  const topbar = (
    <header className="bd-topbar">
      <div className="bd-topbar-left">
        <Link href="/home" className="bd-brand">
          <BrandMark size={28} />
          <span>Rudder</span>
        </Link>
        <nav className="bd-nav">
          <Link href="/home" className="bd-nav-item active">
            Главная
          </Link>
          <Link href="/stats" className="bd-nav-item">
            Статистика
          </Link>
          <Link href="/feedback" className="bd-nav-item">
            Обратная связь
          </Link>
          <Link href="/guides" className="bd-nav-item">
            Обучение
          </Link>
        </nav>
      </div>
      <div className="bd-topbar-right">
        <div className={`bd-balance ${balanceClass(serviceBalance)}`}>
          <CreditCard size={16} />
          <span>
            {serviceBalance === null
              ? '— ₽'
              : `${serviceBalance.toLocaleString('ru-RU')} ₽`}
          </span>
        </div>
        <Link href="/settings">
          <button className="bd-icon-btn" title="Настройки аккаунта">
            <Settings size={20} />
          </button>
        </Link>
      </div>
    </header>
  );

  if (loading) {
    return (
      <div className="bd-page">
        {topbar}
        <div className="bd-scroll">
          <main className="bd-main">
            <div className="bd-state">
              <span className="bd-spin">
                <Loader2 size={32} />
              </span>
              <span>Загружаем настройки бота…</span>
            </div>
          </main>
        </div>
      </div>
    );
  }

  if (notFound || !bot || !derived) {
    return (
      <div className="bd-page">
        {topbar}
        <div className="bd-scroll">
          <main className="bd-main">
            <div className="bd-state">
              <AlertTriangle size={40} />
              <h2>{notFound ? 'Бот не найден' : 'Не удалось открыть бота'}</h2>
              <p>
                {notFound
                  ? 'Возможно, он уже удалён. Настройки удалённых ботов не сохраняются.'
                  : (loadError ?? 'Попробуйте обновить страницу.')}
              </p>
              <Link href="/home">
                <button className="bd-btn bd-btn-ghost">
                  <ArrowLeft size={16} />К моим ботам
                </button>
              </Link>
            </div>
          </main>
        </div>
      </div>
    );
  }

  const directionLabel = bot.direction === 'long' ? 'Лонг' : 'Шорт';
  const openTradesCount = openTrades === null ? null : openTrades.length;
  const profit = stats?.profit ?? bot.total_profit ?? 0;

  return (
    <div className="bd-page">
      {topbar}

      <div className="bd-scroll">
        <main className="bd-main">
          <div className="bd-crumbs">
            <Link href="/home">Главная</Link>
            <span>/</span>
            <Link href="/home">Мои боты</Link>
            <span>/</span>
            <span className="bd-crumbs-current">Настройки бота</span>
          </div>

          {/* ===== Шапка бота ===== */}
          <section className="bd-hero">
            <div className="bd-hero-top">
              <div className="bd-hero-avatar">
                <BotIcon size={24} />
              </div>

              <div className="bd-hero-titles">
                <div className="bd-hero-title-row">
                  <h1>{bot.name}</h1>
                  <span className={`bd-badge ${bot.status}`}>
                    <span className="bd-status-dot" />
                    {STATUS_LABEL[bot.status] ?? bot.status}
                  </span>
                  <span
                    className={`bd-badge ${bot.dry_run ? 'dry' : 'live'}`}
                    title={
                      bot.dry_run
                        ? 'Демо-режим: реальные сделки не совершаются'
                        : 'Боевой режим: сделки идут на бирже'
                    }
                  >
                    {bot.dry_run ? 'Dry Run' : 'Боевой'}
                  </span>
                </div>
                <div className="bd-hero-meta">
                  <strong>{bot.pair}</strong>
                  <span className="bd-dot">•</span>
                  <span>{directionLabel}</span>
                  <span className="bd-dot">•</span>
                  <span>x{bot.leverage}</span>
                  <span className="bd-dot">•</span>
                  <span>{presetLabel(bot.strategy_preset)}</span>
                  <span className="bd-dot">•</span>
                  <span>создан {fmtDate(bot.created_at)}</span>
                </div>
              </div>

              <div className="bd-hero-actions">
                <button
                  className={`bd-btn ${isRunning || isStarting ? 'bd-btn-stop' : 'bd-btn-start'}`}
                  onClick={handleStartStop}
                  disabled={pending || isStarting || startBlocked}
                  title={
                    startBlocked
                      ? `Пополните баланс до ${MIN_SERVICE_BALANCE_RUB} ₽, чтобы запустить бота`
                      : undefined
                  }
                >
                  {pending ? (
                    <span className="bd-spin">
                      <Loader2 size={16} />
                    </span>
                  ) : isRunning || isStarting ? (
                    <Pause size={16} />
                  ) : (
                    <Play size={16} />
                  )}
                  {isRunning || isStarting ? 'Остановить' : 'Запустить'}
                </button>

                <Link href="/stats">
                  <button
                    className="bd-btn bd-btn-square"
                    title="Статистика бота"
                  >
                    <BarChart3 size={16} />
                  </button>
                </Link>

                <button
                  className="bd-btn bd-btn-square danger"
                  onClick={() => setShowDelete(true)}
                  disabled={pending}
                  title="Удалить бота"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </div>

            <div className="bd-kpi-row">
              <div className="bd-kpi">
                <div className="bd-kpi-label">P&amp;L за всё время</div>
                <div
                  className={`bd-kpi-value ${profit >= 0 ? 'profit' : 'loss'}`}
                >
                  {profit >= 0 ? '+' : '−'}${Math.abs(profit).toFixed(2)}
                </div>
              </div>
              <div className="bd-kpi">
                <div className="bd-kpi-label">Сделок</div>
                <div className="bd-kpi-value">{stats?.trades_total ?? '—'}</div>
              </div>
              <div className="bd-kpi">
                <div className="bd-kpi-label">Winrate</div>
                <div className="bd-kpi-value">
                  {stats ? `${stats.winrate.toFixed(1)}%` : '—'}
                </div>
              </div>
              <div className="bd-kpi">
                <div className="bd-kpi-label">В позиции</div>
                {/* 0 и «—» — разные вещи: ноль значит «открытых позиций нет»,
                    прочерк — что список открытых сделок не загрузился. */}
                <div className="bd-kpi-value">{openTradesCount ?? '—'}</div>
              </div>
            </div>
          </section>

          {/* Не только при status="error": бота останавливает из-за баланса и сам
              сервис, статусом "stopped", — причину надо показать в обоих случаях. */}
          {bot.error_message && !isRunning && !isStarting && (
            <div className="bd-banner error">
              <span className="bd-banner-icon">
                <AlertTriangle size={16} />
              </span>
              <span>{bot.error_message}</span>
            </div>
          )}

          {actionError && (
            <div className="bd-banner error">
              <span className="bd-banner-icon">
                <AlertTriangle size={16} />
              </span>
              <span>{actionError}</span>
            </div>
          )}

          {startBlocked && (
            <div className="bd-banner warn">
              <span className="bd-banner-icon">
                <AlertTriangle size={16} />
              </span>
              <span>
                Баланс сервиса ниже {MIN_SERVICE_BALANCE_RUB} ₽ — боевого бота
                запустить нельзя. Пополните баланс в{' '}
                <Link href="/home">панели управления</Link>.
              </span>
            </div>
          )}

          <div className="bd-section-title">
            <h2>Параметры бота</h2>
            <div className="bd-section-spacer" />
            <span className="bd-card-hint">
              Настройки задаются при создании и не меняются у запущенного бота
            </span>
          </div>

          <div className="bd-grid">
            {/* ===== Биржа и режим ===== */}
            <section className="bd-card">
              <div className="bd-card-head">
                <div className="bd-card-icon">
                  <KeyRound size={16} />
                </div>
                <h3>Биржа и режим</h3>
              </div>
              <div className="bd-rows">
                <div className="bd-row">
                  <span className="bd-row-label">Режим торговли</span>
                  <span
                    className={`bd-row-value ${bot.dry_run ? 'accent' : 'loss'}`}
                  >
                    {bot.dry_run ? 'Dry Run (демо)' : 'Боевой'}
                  </span>
                </div>
                <div className="bd-row">
                  <span className="bd-row-label">API-ключ</span>
                  <span className="bd-row-value">{apiKeyName}</span>
                </div>
                <div className="bd-row">
                  <span className="bd-row-label">Торговая пара</span>
                  <span className="bd-row-value">{bot.pair}</span>
                </div>
                <div className="bd-row">
                  <span className="bd-row-label">Направление</span>
                  <span
                    className={`bd-row-value ${bot.direction === 'long' ? 'profit' : 'loss'}`}
                  >
                    {directionLabel}
                  </span>
                </div>
              </div>
            </section>

            {/* ===== Депозит и риск ===== */}
            <section className="bd-card">
              <div className="bd-card-head">
                <div className="bd-card-icon">
                  <DollarSign size={16} />
                </div>
                <h3>Депозит и риск</h3>
              </div>
              <div className="bd-rows">
                <div className="bd-row">
                  <span className="bd-row-label">Депозит бота</span>
                  <span className="bd-row-value">
                    {fmtMoney(derived.deposit)} USDT
                  </span>
                </div>
                <div className="bd-row">
                  <span className="bd-row-label">Размер одной сделки</span>
                  <span className="bd-row-value">
                    {fmtMoney(derived.riskPercent)}% ·{' '}
                    {fmtMoney(derived.margin)} USDT
                  </span>
                </div>
                <div className="bd-row">
                  <span className="bd-row-label">Кредитное плечо</span>
                  <span className="bd-row-value accent">x{bot.leverage}</span>
                </div>
                <div className="bd-row">
                  <span className="bd-row-label">Объём позиции</span>
                  <span className="bd-row-value">
                    {fmtMoney(derived.notional)} USDT
                  </span>
                </div>
              </div>
            </section>

            {/* ===== Стратегия входа ===== */}
            <section className="bd-card wide">
              <div className="bd-card-head">
                <div className="bd-card-icon">
                  <Settings size={16} />
                </div>
                <h3>Стратегия входа</h3>
                <span className="bd-badge neutral">
                  {presetLabel(bot.strategy_preset)}
                </span>
                <div className="bd-section-spacer" />
                <span className="bd-card-hint">
                  Вход, когда выполнены все условия
                </span>
              </div>

              {derived.filters.length > 0 ? (
                <>
                  <div className="bd-filters">
                    {derived.filters.map((f, idx) => (
                      <div className="bd-filter" key={idx}>
                        <span className="bd-filter-ind">
                          {indicatorLabel(f.indicator)}
                        </span>
                        <span className="bd-filter-tf">{f.timeframe}</span>
                        {INDICATOR_META[f.indicator] && (
                          <span className="bd-row-label">
                            период {INDICATOR_META[f.indicator].period}
                          </span>
                        )}
                        <span className="bd-filter-arrow">→</span>
                        <span className="bd-filter-cond">
                          {CONDITION_LABEL[f.condition] ?? f.condition}{' '}
                          <b>{f.value}</b>
                        </span>
                      </div>
                    ))}
                  </div>

                  <div className="bd-note">
                    <span className="bd-note-icon">
                      <Info size={15} />
                    </span>
                    <span>
                      Бот открывает {bot.direction === 'long' ? 'лонг' : 'шорт'}{' '}
                      по паре {bot.pair}, когда{' '}
                      {derived.filters
                        .map(
                          (f) =>
                            `${indicatorLabel(f.indicator)} ${f.timeframe} ${
                              CONDITION_LABEL[f.condition] ?? f.condition
                            } ${f.value}`,
                        )
                        .join(' и ')}
                      . Условия проверяются на закрытии свечи.
                    </span>
                  </div>
                </>
              ) : (
                <div className="bd-empty">
                  Условия входа для направления «{directionLabel}» не заданы
                </div>
              )}
            </section>

            {/* ===== Выход из сделки ===== */}
            <section className="bd-card">
              <div className="bd-card-head">
                <div className="bd-card-icon">
                  <Target size={16} />
                </div>
                <h3>Выход из сделки</h3>
              </div>

              <div className="bd-exit-grid">
                <div className="bd-exit-box tp">
                  <div className="bd-exit-kicker">TAKE PROFIT</div>
                  <div className="bd-exit-value">
                    {derived.tp === null ? '—' : `+${derived.tp}%`}
                  </div>
                  <div className="bd-exit-hint">
                    {derived.tpMoney === null
                      ? 'Бот создан до появления этой настройки'
                      : `≈ +${fmtMoney(derived.tpMoney)} USDT`}
                  </div>
                </div>

                <div className={`bd-exit-box ${derived.slEnabled ? 'sl' : ''}`}>
                  <div className="bd-exit-kicker">STOP LOSS</div>
                  <div className="bd-exit-value">
                    {derived.slEnabled ? `−${derived.sl}%` : 'Отключён'}
                  </div>
                  <div className="bd-exit-hint">
                    {derived.slMoney === null
                      ? 'Позиция закрывается по take profit или вручную'
                      : `≈ −${fmtMoney(derived.slMoney)} USDT`}
                  </div>
                </div>
              </div>

              <div className="bd-note">
                <span className="bd-note-icon">
                  <Info size={15} />
                </span>
                <span>
                  Проценты — это движение цены, а не доля депозита: плечо на них
                  не влияет, оно только умножает результат сделки.
                </span>
              </div>
            </section>

            {/* ===== Что это значит на самом деле ===== */}
            <section className="bd-card">
              <div className="bd-card-head">
                <div className="bd-card-icon">
                  <ClipboardList size={16} />
                </div>
                <h3>Что это значит на самом деле</h3>
              </div>

              <div className="bd-rows">
                <div className="bd-row">
                  <span className="bd-row-label">Прибыль по take profit</span>
                  <span className="bd-row-value profit">
                    {derived.tpOfMargin === null
                      ? '—'
                      : `+${fmtMoney(derived.tpOfMargin)}% от денег в сделке`}
                  </span>
                </div>
                <div className="bd-row">
                  <span className="bd-row-label">Убыток по стопу</span>
                  <span
                    className={`bd-row-value ${derived.slOfMargin === null ? 'muted' : 'loss'}`}
                  >
                    {derived.slOfMargin === null
                      ? 'нет стоп-лосса'
                      : `−${fmtMoney(derived.slOfMargin)}% от денег в сделке`}
                  </span>
                </div>
                <div className="bd-row">
                  <span className="bd-row-label">Комиссия биржи за круг</span>
                  <span className="bd-row-value warn">
                    ≈ {fmtMoney(derived.feeOfMargin)}% от денег в сделке
                  </span>
                </div>
                <div className="bd-row">
                  <span className="bd-row-label">Движение цены до TP</span>
                  <span className="bd-row-value">
                    {derived.tp === null ? '—' : `${fmtMoney(derived.tp)}%`}
                  </span>
                </div>
                <div className="bd-row">
                  <span className="bd-row-label">Ликвидация примерно при</span>
                  <span className="bd-row-value loss">
                    {fmtMoney(derived.liquidationMove)}% движения цены против
                    позиции
                  </span>
                </div>
              </div>

              <div className="bd-risk-head">
                <span className="bd-risk-label">Уровень риска</span>
                <span
                  className="bd-risk-value"
                  style={{ color: derived.riskColor }}
                >
                  {derived.riskLabel}
                </span>
              </div>
              <div className="bd-risk-bar">
                <span
                  style={{
                    width: `${derived.riskScore}%`,
                    background: derived.riskColor,
                  }}
                />
              </div>
            </section>

            <div className="bd-footer-bar">
              <span>Бот создан {fmtDate(bot.created_at)}</span>
              <div className="bd-footer-spacer" />
              <Link href="/stats">Статистика и сделки</Link>
              <Link href="/guides">Как это работает</Link>
            </div>
          </div>

          <SiteFooter />
        </main>
      </div>

      {/* ===== Модалка удаления ===== */}
      {showDelete && (
        <div className="bd-modal-overlay" onClick={() => setShowDelete(false)}>
          <div className="bd-modal" onClick={(e) => e.stopPropagation()}>
            <h2>Удалить бота?</h2>
            <p>
              Бот будет остановлен и удалён. История сделок сохранится в
              статистике, но восстановить настройки нельзя.
            </p>

            {/* Предупреждаем только по боевому боту: в демо «открытая сделка»
                живёт лишь в базе freqtrade, на бирже терять нечего. */}
            {!bot.dry_run && openTrades && openTrades.length > 0 && (
              <div className="bd-open-trade">
                У бота {openTrades.length}{' '}
                {openTrades.length === 1
                  ? 'открытая сделка'
                  : 'открытых сделок'}{' '}
                на бирже. После удаления позицию придётся закрывать вручную:
                сервис потеряет связь с ней.
              </div>
            )}

            <div className="bd-modal-actions">
              <button
                className="bd-btn bd-btn-ghost"
                onClick={() => setShowDelete(false)}
                disabled={pending}
              >
                Отмена
              </button>
              <button
                className="bd-btn bd-btn-danger"
                onClick={handleDelete}
                disabled={pending}
              >
                {pending ? (
                  <span className="bd-spin">
                    <Loader2 size={16} />
                  </span>
                ) : (
                  <Trash2 size={16} />
                )}
                Удалить
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
