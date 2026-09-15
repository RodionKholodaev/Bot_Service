'use client';
import React, { useState, useEffect, useCallback } from 'react';
import { BrandMark } from '@/app/components/BrandMark';
import {
  TrendingUp,
  Bot,
  Wallet,
  DollarSign,
  Plus,
  Settings,
  BookOpen,
  MessageCircle,
  BarChart3,
  Pause,
  Play,
  AlertCircle,
  ChevronRight,
  CreditCard,
  Loader2,
  Trash2,
  AlertTriangle,
  FlaskConical,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { MIN_SERVICE_BALANCE_RUB, presetLabel } from '@/lib/constants';
import { apiFetch } from '@/lib/api';
import { SiteFooter } from '@/app/components/SiteFooter';
import { formatSignedUsd } from '@/lib/money';
// ── Типы под BotPublic с бэка ─────────────────────────────
type BotStatus = 'created' | 'starting' | 'running' | 'stopped' | 'error';

interface BotPublic {
  id: string;
  name: string;
  pair: string;
  leverage: number;
  direction: string;
  strategy_preset: string;
  entry_filters_long: Array<Record<string, unknown>>;
  entry_filters_short: Array<Record<string, unknown>>;
  // Проценты движения цены, как их задал человек. null — у ботов, созданных до
  // появления этих полей: у них в базе только формат freqtrade.
  take_profit_percent: number | null;
  stop_loss_percent: number | null;
  dry_run: boolean;
  status: BotStatus;
  error_message: string | null;
  api_port: number;
  created_at: string;
  total_profit?: number;
}

// Открытая сделка бота — GET /bots/{id}/open-trades. Нужна только диалогу удаления.
interface OpenTrade {
  pair: string;
  direction: string;
  open_rate: number;
  amount: number;
  open_time: string;
}

interface HomeStats {
  service_balance: number;
  total_profit: number;
  bots_running: number;
  bots_total: number;
  weekly_profit: number;
  funds_under_management: number;
}

// Запросы идут через apiFetch (lib/api.ts): он же подставляет токен и он же
// сбрасывает сессию на 401 — руками собранный заголовок этого не умел.

const TradingBotDashboard = () => {
  // null — баланс ещё не загружен (или запрос упал). Отличать это от нуля
  // обязательно: иначе на первом рендере 0 < порога и страница показывает
  // баннер «баланс ниже 100 ₽» пользователю, у которого баланс в порядке.
  const [serviceBalance, setServiceBalance] = useState<number | null>(null);
  // статистика
  const [homeStats, setHomeStats] = useState<HomeStats | null>(null);
  const router = useRouter();

  // проверка того что пользователь имеет JWT
  useEffect(() => {
    if (!localStorage.getItem('access_token')) {
      router.replace('/auth');
    }
  }, [router]);

  const fetchBalance = useCallback(async () => {
    try {
      const data = await apiFetch<{ service_balance: number }>(
        '/users/me/balance',
        { cache: 'no-store' },
      );
      setServiceBalance(data.service_balance);
    } catch (e) {
      console.error('Не удалось загрузить баланс:', e);
    }
  }, []);

  const fetchHomeStats = useCallback(async () => {
    try {
      const data = await apiFetch<HomeStats>('/stats/home', {
        cache: 'no-store',
      });
      setHomeStats(data);
    } catch (e) {
      console.error('Не удалось загрузить статистику:', e);
    }
  }, []);

  // Ниже порога сервис останавливает боевых ботов и не даёт создавать новых
  // (см. backend/src/services/balance_guard.py). Здесь это только предупреждение
  // и погашенные кнопки — отказ всё равно выносит бэкенд, 402-м ответом.
  const lowBalance =
    serviceBalance !== null && serviceBalance < MIN_SERVICE_BALANCE_RUB;

  const [showTopUpModal, setShowTopUpModal] = useState(false);

  // --------оплата-----
  const [topUpAmount, setTopUpAmount] = useState<string>('');
  const [topUpLoading, setTopUpLoading] = useState(false);

  // ── Боты с бэка ─────────────────────────────────────────
  const [bots, setBots] = useState<BotPublic[]>([]);
  const [botsLoading, setBotsLoading] = useState(true);
  const [botsError, setBotsError] = useState<string | null>(null);
  // id ботов, по которым сейчас идёт start/stop/delete — чтобы блокировать кнопки
  const [pendingIds, setPendingIds] = useState<Set<string>>(new Set());
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  // Открытые сделки удаляемого бота. Удаление сносит папку бота вместе с базой
  // freqtrade, а позиция остаётся на бирже — и связать её с сервисом больше нечем,
  // поэтому спрашиваем до удаления, а не после. null — проверка ещё не дала ответа.
  const [openTrades, setOpenTrades] = useState<OpenTrade[] | null>(null);
  const [openTradesLoading, setOpenTradesLoading] = useState(false);

  const askDeleteConfirm = async (botId: string) => {
    setDeleteConfirmId(botId);
    setOpenTrades(null);
    setOpenTradesLoading(true);
    try {
      setOpenTrades(
        await apiFetch<OpenTrade[]>(`/bots/${botId}/open-trades`, {
          cache: 'no-store',
        }),
      );
    } catch (e) {
      // Оставляем null: молча сказать «открытых сделок нет» нельзя — мы этого не знаем.
      console.error('Не удалось проверить открытые сделки:', e);
      setOpenTrades(null);
    } finally {
      setOpenTradesLoading(false);
    }
  };

  // Функция создания платежа:
  const handleTopUp = async () => {
    const amount = parseFloat(topUpAmount);
    if (!amount || amount < 10) return alert('Минимальная сумма — 10 ₽');

    setTopUpLoading(true);
    try {
      const data = await apiFetch<{ confirmation_url: string }>(
        '/payments/create',
        { method: 'POST', body: { amount } },
      );
      // Редиректим пользователя на страницу оплаты ЮКассы
      window.location.href = data.confirmation_url;
    } catch (e) {
      console.error(e);
      alert('Ошибка при создании платежа');
    } finally {
      setTopUpLoading(false);
    }
  };

  const fetchBots = useCallback(async () => {
    try {
      setBotsError(null);
      const data = await apiFetch<BotPublic[]>('/bots', {
        cache: 'no-store',
      });
      setBots(data);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Неизвестная ошибка';
      setBotsError(`Не удалось загрузить ботов: ${msg}`);
    } finally {
      setBotsLoading(false);
    }
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('payment') === 'success') {
      // Ждём 3 секунды перед запросом баланса
      setTimeout(() => fetchBalance(), 3000);

      // Убираем параметр ?payment=success из URL
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);

  useEffect(() => {
    if (!localStorage.getItem('access_token')) return;
    // Обычная загрузка данных при монтировании: setState происходит уже после
    // await внутри каждой из функций, каскадного ререндера нет. Правило этого
    // не различает и ругается на любой вызов функции с setState внутри.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchBots();
    fetchBalance();
    fetchHomeStats();
    // авто-обновление раз в 15 секунд, чтобы видеть смену статусов
    const interval = setInterval(fetchBots, 15000);
    return () => clearInterval(interval);
  }, [fetchBots, fetchBalance, fetchHomeStats]);

  const markPending = (id: string, on: boolean) => {
    setPendingIds((prev) => {
      const next = new Set(prev);
      on ? next.add(id) : next.delete(id);
      return next;
    });
  };

  const handleStartStop = async (bot: BotPublic) => {
    const action =
      bot.status === 'running' || bot.status === 'starting' ? 'stop' : 'start';
    markPending(bot.id, true);
    try {
      const updated = await apiFetch<BotPublic>(`/bots/${bot.id}/${action}`, {
        method: 'POST',
      });
      setBots((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
    } catch (e) {
      console.error(e);
      // мягкий фоллбэк — просто перечитаем список
      fetchBots();
      // и баланс: одна из причин отказа — что он ушёл ниже порога, пока страница
      // была открыта. Перечитав его, показываем баннер вместо молчаливой ошибки.
      fetchBalance();
    } finally {
      markPending(bot.id, false);
    }
  };

  const handleDelete = async (botId: string) => {
    markPending(botId, true);
    try {
      await apiFetch(`/bots/${botId}`, { method: 'DELETE' });
      const deletedBot = bots.find((b) => b.id === botId);
      setBots((prev) => prev.filter((b) => b.id !== botId));
      setHomeStats((prev) => {
        if (!prev) return prev;
        const wasActive =
          deletedBot?.status === 'running' || deletedBot?.status === 'starting';
        return {
          ...prev,
          bots_total: Math.max(0, prev.bots_total - 1),
          bots_running: wasActive
            ? Math.max(0, prev.bots_running - 1)
            : prev.bots_running,
        };
      });
      // подтягиваем актуальные цифры с бэка на случай расхождения
      fetchHomeStats();
    } catch (e) {
      console.error(e);
      fetchBots();
    } finally {
      markPending(botId, false);
      setDeleteConfirmId(null);
    }
  };

  // ── Производные метрики для верхних карточек ───────────
  const stats = {
    activeBots:
      homeStats?.bots_running ??
      bots.filter((b) => b.status === 'running' || b.status === 'starting')
        .length,
    weeklyProfit: homeStats?.weekly_profit ?? 0,
    fundsUnderManagement: homeStats?.funds_under_management ?? 0,
  };

  const getBalanceStatus = (balance: number | null) => {
    if (balance === null)
      return { color: 'gray', daysLeft: 0, status: 'loading' };
    if (balance < 100) return { color: 'red', daysLeft: 1, status: 'critical' };
    if (balance < 1000) return { color: 'orange', daysLeft: 5, status: 'low' };
    return { color: 'green', daysLeft: 14, status: 'good' };
  };

  const balanceStatus = getBalanceStatus(serviceBalance);

  return (
    <div className="dashboard-container">
      {/* Critical Balance Alert */}
      {/* {balanceStatus.status === 'critical' && (
        <div className="balance-alert critical">
          <AlertCircle size={20} />
          <span>⚠️ Критический баланс! Боты остановятся через {balanceStatus.daysLeft} день. Пополните баланс сейчас.</span>
          <button className="btn-alert-action" onClick={() => setShowTopUpModal(true)}>
            Пополнить сейчас
          </button>
        </div>
      )} */}

      {/* {balanceStatus.status === 'low' && (
        <div className="balance-alert warning">
          <AlertCircle size={18} />
          <span>Баланс заканчивается. Хватит примерно на {balanceStatus.daysLeft} дней работы.</span>
          <button className="btn-alert-action-small" onClick={() => setShowTopUpModal(true)}>
            Пополнить
          </button>
        </div>
      )} */}

      {/* Header */}
      <header className="dashboard-header">
        <div className="header-left">
          <div className="logo">
            <BrandMark size={28} />
            <span>Rudder</span>
          </div>
          <nav className="main-nav">
            <a href="#" className="nav-item active">
              Главная
            </a>
            {/* span внутри Link обязателен: styled-jsx не скоупит классы на React-компоненты */}
            <Link href="/stats">
              <span className="nav-item">Статистика</span>
            </Link>
            <Link href="/feedback">
              <span className="nav-item">Обратная связь</span>
            </Link>
            <Link href="/guides">
              <span className="nav-item">Обучение</span>
            </Link>
          </nav>
        </div>
        <div className="header-right">
          <div
            className={`balance-indicator ${balanceStatus.status}`}
            onClick={() => setShowTopUpModal(true)}
          >
            <CreditCard size={16} />
            <span className="balance-amount">
              {serviceBalance === null
                ? '— ₽'
                : `${serviceBalance.toLocaleString('ru-RU')} ₽`}
            </span>
          </div>
          <button
            className="btn-icon"
            onClick={() => setShowTopUpModal(true)}
            aria-label="Пополнить баланс"
          >
            <Plus size={20} />
          </button>
          <Link href="/settings">
            <button className="btn-icon" aria-label="Настройки">
              <Settings size={20} />
            </button>
          </Link>
        </div>
      </header>

      {/* Main Content */}
      <div className="dashboard-scroll">
        <main className="dashboard-main">
          {/* Hero Section */}
          <section className="home-hero-section">
            <div className="home-hero-content">
              <h1>Добро пожаловать в панель управления</h1>
              <p>Ваши торговые боты работают круглосуточно</p>
            </div>
            <div className="home-hero-actions">
              {/* Кнопку не гасим даже при низком балансе: порог закрывает только
                  боевых ботов, демо создавать можно всегда (см.
                  backend/src/services/balance_guard.py). Про боевой режим
                  предупреждает и отказывает уже страница создания. */}
              <Link href="/bot-creation">
                <button className="btn-primary">
                  <Plus size={20} />
                  Создать бота
                </button>
              </Link>
              {/* <button className="btn-secondary">
              <BookOpen size={20} />
              Как это работает?
            </button> */}
            </div>
          </section>

          {lowBalance && (
            <section className="low-balance-banner">
              {/* обёртка обязательна: styled-jsx не скоупит класс, повешенный
                  на React-компонент, — стиль до иконки просто не дойдёт */}
              <span className="low-balance-icon">
                <AlertTriangle size={20} />
              </span>
              <span className="low-balance-text">
                Баланс сервиса ниже {MIN_SERVICE_BALANCE_RUB} ₽ — боевые боты
                остановлены, новых создать нельзя. Демо-ботов это не касается:
                они работают и создаются как обычно.
              </span>
              <button
                className="btn-text low-balance-action"
                onClick={() => setShowTopUpModal(true)}
              >
                Пополнить
              </button>
            </section>
          )}

          {/* Stats Grid */}
          <section className="stats-grid">
            <div className="stat-card">
              <div className="stat-icon">
                <Bot size={24} />
              </div>
              <div className="stat-content">
                <div className="stat-label">Активные боты</div>
                <div className="stat-value">{stats.activeBots}</div>
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-icon">
                <TrendingUp size={24} />
              </div>
              <div className="stat-content">
                <div className="stat-label">Прибыль за неделю</div>
                <div className="stat-value">
                  {formatSignedUsd(stats.weeklyProfit)}
                </div>
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-icon">
                <DollarSign size={24} />
              </div>
              <div className="stat-content">
                <div className="stat-label">В управлении</div>
                <div className="stat-value">
                  $
                  {stats.fundsUnderManagement.toLocaleString('en-US', {
                    minimumFractionDigits: 2,
                  })}
                </div>
              </div>
            </div>

            {/* <div className="stat-card">
            <div className="stat-icon">
              <Wallet size={24} />
            </div>
            <div className="stat-content">
              <div className="stat-label">Баланс на бирже</div>
              <div className="stat-value">${stats.exchangeBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
            </div>
          </div> */}
          </section>

          {/* Active Bots */}
          <section className="bots-section">
            <div className="section-header">
              <h2>Мои боты</h2>
              {/* <button className="btn-text" onClick={fetchBots} disabled={botsLoading}>
              Обновить <ChevronRight size={16} />
            </button> */}
            </div>

            {botsLoading && bots.length === 0 ? (
              <div className="bots-loading">
                <Loader2 size={32} className="spin" />
                <span>Загружаем ботов...</span>
              </div>
            ) : botsError ? (
              <div className="bots-error">
                <AlertTriangle size={20} />
                <span>{botsError}</span>
                <button className="btn-text" onClick={fetchBots}>
                  Повторить
                </button>
              </div>
            ) : bots.length > 0 ? (
              <div className="bots-list">
                {bots.map((bot) => {
                  const isPending = pendingIds.has(bot.id);
                  const isRunning = bot.status === 'running';
                  const isStarting = bot.status === 'starting';
                  const isStopped =
                    bot.status === 'stopped' || bot.status === 'created';

                  const statusLabel: Record<BotStatus, string> = {
                    running: 'Работает',
                    starting: 'Запускается',
                    stopped: 'Остановлен',
                    created: 'Создан',
                    error: 'Ошибка',
                  };

                  // Остановить можно всегда, запустить — нет: боевого бота
                  // бэкенд при таком балансе всё равно отобьёт.
                  const startBlocked =
                    lowBalance && !bot.dry_run && !isRunning && !isStarting;

                  const profit = bot.total_profit ?? 0;

                  return (
                    <div
                      key={bot.id}
                      className={`bot-card status-${bot.status}`}
                    >
                      <div className="bot-header">
                        <div className="bot-info">
                          <div className="bot-title-block">
                            <div className="bot-title-row">
                              <h3>{bot.name}</h3>
                              {bot.dry_run && (
                                <span
                                  className="badge badge-dry"
                                  title="Демо-режим, реальные сделки не совершаются"
                                >
                                  <FlaskConical size={12} />
                                  DEMO
                                </span>
                              )}
                            </div>
                            <p className="bot-meta">
                              <span>{bot.pair}</span>
                              <span>{bot.direction}</span>
                              <span>x{bot.leverage}</span>
                              <span>{presetLabel(bot.strategy_preset)}</span>
                              {bot.take_profit_percent !== null && (
                                <>
                                  <span>TP {bot.take_profit_percent}%</span>
                                  <span>
                                    {bot.stop_loss_percent !== null
                                      ? `SL ${bot.stop_loss_percent}%`
                                      : 'без SL'}
                                  </span>
                                </>
                              )}
                            </p>
                          </div>
                        </div>
                        <div className="bot-actions">
                          <button
                            className="btn-icon-small"
                            onClick={() => handleStartStop(bot)}
                            disabled={isPending || isStarting || startBlocked}
                            title={
                              startBlocked
                                ? `Пополните баланс до ${MIN_SERVICE_BALANCE_RUB} ₽, чтобы запустить бота`
                                : isRunning
                                  ? 'Остановить'
                                  : 'Запустить'
                            }
                          >
                            {isPending ? (
                              <Loader2 size={16} className="spin" />
                            ) : isRunning || isStarting ? (
                              <Pause size={16} />
                            ) : (
                              <Play size={16} />
                            )}
                          </button>
                          <Link href={`/bot/${bot.id}`}>
                            <button
                              className="btn-icon-small"
                              title="Настройки"
                              aria-label="Настройки"
                            >
                              <Settings size={16} />
                            </button>
                          </Link>
                          <button
                            className="btn-icon-small btn-icon-danger"
                            onClick={() => askDeleteConfirm(bot.id)}
                            disabled={isPending}
                            title="Удалить"
                            aria-label="Удалить"
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </div>

                      <div className={`bot-status-row status-${bot.status}`}>
                        <span className="status-text">
                          {statusLabel[bot.status]}
                        </span>
                        {/* Не только при status="error": сервис останавливает бота
                            из-за баланса штатно, статусом "stopped", и причину
                            пользователь должен увидеть там же. */}
                        {bot.error_message && !isRunning && !isStarting && (
                          <span
                            className="status-error-msg"
                            title={bot.error_message}
                          >
                            — {bot.error_message}
                          </span>
                        )}
                      </div>

                      <div className="bot-stats">
                        <div className="bot-stat">
                          <span className="bot-stat-label">Прибыль</span>
                          <span className="bot-stat-value">
                            {formatSignedUsd(profit)}
                          </span>
                        </div>
                        <Link href={`/bot/${bot.id}`}>
                          <button className="btn-bot-details">
                            <BarChart3 size={16} />
                            Подробнее
                          </button>
                        </Link>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="empty-state">
                <Bot size={64} />
                <h3>У вас пока нет ботов</h3>
                <p>Создайте своего первого торгового бота за пару минут</p>
                <Link href="/bot-creation">
                  <button className="btn-primary">
                    <Plus size={20} />
                    Создать первого бота
                  </button>
                </Link>
              </div>
            )}
          </section>

          {/* Quick Actions */}
          <section className="quick-actions">
            {/* <button className="action-card">
            <MessageCircle size={24} />
            <div>
              <h3>Поддержка</h3>
              <p>Задать вопрос</p>
            </div>
            <ChevronRight size={20} />
          </button> */}
            <Link href="/stats" style={{ display: 'contents' }}>
              <button className="action-card">
                <BarChart3 size={24} />
                <div>
                  <h3>Детальная статистика</h3>
                  <p>Анализ и графики</p>
                </div>
                <ChevronRight size={20} />
              </button>
            </Link>
            <Link href="/guides" style={{ display: 'contents' }}>
              <button className="action-card">
                <BookOpen size={24} />
                <div>
                  <h3>Обучение</h3>
                  <p>Гайды для новичков</p>
                </div>
                <ChevronRight size={20} />
              </button>
            </Link>
          </section>
          <SiteFooter />
        </main>
      </div>

      {/* Delete confirmation modal */}
      {deleteConfirmId &&
        (() => {
          const botToDelete = bots.find((b) => b.id === deleteConfirmId);
          // Предупреждаем только по боевому боту: в демо-режиме «открытая сделка»
          // живёт лишь в базе freqtrade, на бирже терять нечего.
          const liveOpenTrades =
            botToDelete && !botToDelete.dry_run && openTrades ? openTrades : [];

          return (
            <div
              className="modal-overlay"
              onClick={() => setDeleteConfirmId(null)}
            >
              <div
                className="modal-content"
                onClick={(e) => e.stopPropagation()}
              >
                <h2>Удалить бота?</h2>
                <p className="modal-description">
                  Бот будет остановлен и удалён. История сделок сохранится в
                  статистике, но восстановить настройки нельзя.
                </p>

                {openTradesLoading && (
                  <p className="modal-description">
                    Проверяем открытые сделки...
                  </p>
                )}

                {!openTradesLoading && liveOpenTrades.length > 0 && (
                  <div className="delete-open-trades-warning">
                    <AlertTriangle size={16} />
                    <span>
                      На бирже открыто сделок: {liveOpenTrades.length} (
                      {liveOpenTrades.map((t) => t.pair).join(', ')}). Удаление
                      не закрывает позицию: бот перестанет ей управлять,
                      тейк-профит не сработает, и закрыть её можно будет только
                      вручную на Bybit. Стоп-лосс, выставленный на бирже,
                      продолжит действовать. Чтобы бот довёл сделку сам, сначала
                      дождитесь её закрытия.
                    </span>
                  </div>
                )}

                <div className="modal-actions">
                  <button
                    className="btn-secondary"
                    onClick={() => setDeleteConfirmId(null)}
                  >
                    Отмена
                  </button>
                  <button
                    className="btn-danger"
                    onClick={() =>
                      deleteConfirmId && handleDelete(deleteConfirmId)
                    }
                    // Пока не знаем про открытые сделки — удалять рано:
                    // предупреждение появится через долю секунды.
                    disabled={
                      pendingIds.has(deleteConfirmId) || openTradesLoading
                    }
                  >
                    {pendingIds.has(deleteConfirmId) ? (
                      <Loader2 size={16} className="spin" />
                    ) : (
                      <Trash2 size={16} />
                    )}
                    {liveOpenTrades.length > 0
                      ? 'Всё равно удалить'
                      : 'Удалить'}
                  </button>
                </div>
              </div>
            </div>
          );
        })()}

      {/* Top-up Modal */}
      {showTopUpModal && (
        <div className="modal-overlay" onClick={() => setShowTopUpModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Пополнить баланс</h2>
            <p className="modal-description">
              Выберите сумму пополнения или введите свою
            </p>

            <div className="topup-amounts">
              {[500, 1000, 2000, 5000].map((val) => (
                <button
                  key={val}
                  className={`amount-btn ${topUpAmount === String(val) ? 'selected' : ''} ${val === 1000 ? 'recommended' : ''}`}
                  onClick={() => setTopUpAmount(String(val))}
                >
                  {val.toLocaleString('ru-RU')} ₽
                </button>
              ))}
            </div>

            <div className="custom-amount">
              <label>Или введите сумму</label>
              <input
                type="number"
                placeholder="1000"
                value={topUpAmount}
                onChange={(e) => setTopUpAmount(e.target.value)}
                min={10}
              />
            </div>

            <div className="modal-actions">
              <button
                className="btn-secondary"
                onClick={() => setShowTopUpModal(false)}
              >
                Отмена
              </button>
              <button
                className="btn-primary"
                onClick={handleTopUp}
                disabled={topUpLoading || !topUpAmount}
              >
                {topUpLoading ? <Loader2 size={16} className="spin" /> : null}
                Пополнить
              </button>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        * {
          margin: 0;
          padding: 0;
          box-sizing: border-box;
        }

        .dashboard-container {
          height: 100dvh;
          display: flex;
          flex-direction: column;
          overflow: hidden;
          background: var(--bg-page);
          color: var(--text);
        }

        /* Balance Alert */
        .balance-alert {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 16px 24px;
          font-size: 14px;
          font-weight: 500;
        }

        .balance-alert.critical {
          background: color-mix(in srgb, var(--danger-strong) 15%, transparent);
          border-bottom: 2px solid
            color-mix(in srgb, var(--danger-strong) 50%, transparent);
          color: var(--danger);
        }

        .balance-alert.warning {
          background: color-mix(in srgb, var(--warning) 10%, transparent);
          border-bottom: 2px solid
            color-mix(in srgb, var(--warning) 30%, transparent);
          color: var(--warning);
        }

        .btn-alert-action,
        .btn-alert-action-small {
          margin-left: auto;
          padding: 8px 20px;
          border: none;
          border-radius: var(--radius-md);
          font-weight: 600;
          cursor: pointer;
          transition:
            background-color 0.2s,
            transform 0.2s;
        }

        .btn-alert-action {
          background: var(--danger-strong);
          color: var(--text-on-accent);
          font-size: 14px;
        }

        .btn-alert-action-small {
          background: color-mix(in srgb, var(--warning) 20%, transparent);
          color: var(--warning);
          font-size: 13px;
          border: 1px solid color-mix(in srgb, var(--warning) 30%, transparent);
        }

        .btn-alert-action:hover {
          background: color-mix(in srgb, var(--danger-strong) 85%, black);
          transform: translateY(-1px);
        }

        .btn-alert-action-small:hover {
          background: color-mix(in srgb, var(--warning) 30%, transparent);
        }

        /* Header */
        .dashboard-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 20px 40px;
          background: var(--bg-card);
          backdrop-filter: blur(20px);
          border-bottom: 1px solid var(--border-subtle);
          flex-shrink: 0;
        }

        .header-left {
          display: flex;
          align-items: center;
          gap: 48px;
        }

        .logo {
          display: flex;
          align-items: center;
          gap: 12px;
          font-size: 22px;
          font-weight: 700;
          color: var(--accent-soft);
        }

        .main-nav {
          display: flex;
          gap: 8px;
        }

        .nav-item {
          padding: 8px 16px;
          color: var(--text-secondary);
          text-decoration: none;
          border-radius: var(--radius-md);
          font-size: 14px;
          font-weight: 500;
          transition:
            color 0.2s,
            background-color 0.2s;
          display: inline-flex;
          align-items: center;
        }

        .nav-item:hover {
          color: var(--text);
          background: var(--bg-subtle);
        }

        .nav-item.active {
          color: var(--accent-soft);
          background: color-mix(in srgb, var(--accent-soft) 10%, transparent);
        }

        .header-right {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .balance-indicator {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 12px 20px;
          border-radius: var(--radius-lg);
          font-weight: 600;
          font-size: 15px;
          cursor: pointer;
          transition:
            transform 0.2s,
            box-shadow 0.2s;
          border: 1.5px solid;
          font-variant-numeric: tabular-nums;
        }

        .balance-indicator.good {
          background: color-mix(
            in srgb,
            var(--success-strong) 10%,
            transparent
          );
          border-color: color-mix(
            in srgb,
            var(--success-strong) 30%,
            transparent
          );
          color: var(--success);
        }

        .balance-indicator.low {
          background: color-mix(in srgb, var(--warning) 10%, transparent);
          border-color: color-mix(in srgb, var(--warning) 30%, transparent);
          color: var(--warning);
        }

        .balance-indicator.critical {
          background: color-mix(in srgb, var(--danger-strong) 10%, transparent);
          border-color: color-mix(
            in srgb,
            var(--danger-strong) 40%,
            transparent
          );
          color: var(--danger);
          animation: pulse-critical 2s ease-in-out infinite;
        }

        @keyframes pulse-critical {
          0%,
          100% {
            box-shadow: 0 0 0 0
              color-mix(in srgb, var(--danger-strong) 40%, transparent);
          }
          50% {
            box-shadow: 0 0 0 8px transparent;
          }
        }

        .balance-indicator:hover {
          transform: translateY(-2px);
          box-shadow: var(--shadow-md);
        }

        .btn-icon {
          padding: 8px;
          background: var(--bg-subtle);
          border: 1px solid var(--border);
          border-radius: var(--radius-lg);
          color: var(--text-secondary);
          cursor: pointer;
          transition:
            background-color 0.2s,
            color 0.2s,
            transform 0.2s;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .btn-icon:hover {
          background: var(--bg-hover);
          color: var(--text);
          transform: translateY(-1px);
        }

        /* Main Content */
        .dashboard-scroll {
          flex: 1;
          overflow-y: auto;
          scrollbar-width: thin;
          scrollbar-color: var(--scrollbar-thumb) var(--bg-subtle);
        }

        .dashboard-scroll::-webkit-scrollbar {
          width: 4px;
        }

        .dashboard-scroll::-webkit-scrollbar-track {
          background: var(--bg-subtle);
        }

        .dashboard-scroll::-webkit-scrollbar-thumb {
          background: var(--scrollbar-thumb);
          border-radius: var(--radius-sm);
        }

        .dashboard-scroll::-webkit-scrollbar-thumb:hover {
          background: var(--scrollbar-thumb-hover);
        }

        .dashboard-main {
          padding: 40px;
          max-width: 1400px;
          margin: 0 auto;
        }

        /* Hero Section */
        .home-hero-section {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 40px;
          padding: 32px;
          background: var(--bg-card);
          border-radius: var(--radius-xl);
          border: 1px solid var(--border-subtle);
          animation: fadeIn 0.6s ease-out;
        }

        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .home-hero-content h1 {
          font-size: 32px;
          font-weight: 700;
          margin-bottom: 8px;
          color: var(--text);
        }

        .home-hero-content p {
          color: var(--text-secondary);
          font-size: 16px;
        }

        .home-hero-actions {
          display: flex;
          gap: 12px;
        }

        .btn-primary,
        .btn-secondary {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 12px 24px;
          border-radius: var(--radius-lg);
          font-weight: 600;
          font-size: 15px;
          cursor: pointer;
          transition:
            background-color 0.2s,
            transform 0.2s,
            box-shadow 0.2s;
          border: none;
        }

        .btn-primary {
          background: var(--accent);
          color: var(--text-on-accent);
          box-shadow: var(--shadow-sm);
        }

        .btn-primary:hover {
          background: var(--accent-hover);
          transform: translateY(-2px);
          box-shadow: var(--shadow-md);
        }

        .btn-secondary {
          background: var(--bg-subtle);
          color: var(--text);
          border: 1px solid var(--border);
        }

        .btn-secondary:hover {
          background: var(--bg-hover);
          transform: translateY(-2px);
        }

        /* Low Balance Banner */
        /* Стоит между hero и сеткой статистики: у hero margin-bottom: 40px,
           столько же снизу здесь — баннер оказывается ровно посередине. */
        .low-balance-banner {
          display: flex;
          align-items: center;
          justify-content: center;
          flex-wrap: wrap;
          gap: 12px;
          margin: 0 0 40px;
          padding: 16px 24px;
          text-align: center;
          background: color-mix(in srgb, var(--warning) 10%, transparent);
          border: 1px solid color-mix(in srgb, var(--warning) 30%, transparent);
          border-radius: var(--radius-xl);
          animation: slideUp 0.6s ease-out;
        }

        .low-balance-icon {
          display: flex;
          color: var(--warning);
          flex-shrink: 0;
        }

        .low-balance-text {
          color: var(--warning);
          font-size: 15px;
          font-weight: 500;
        }

        .low-balance-action {
          text-decoration: underline;
        }

        /* Stats Grid */
        .stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 20px;
          margin-bottom: 40px;
        }

        .stat-card {
          background: var(--bg-card);
          border: 1px solid var(--border-subtle);
          border-radius: var(--radius-xl);
          padding: 24px;
          display: flex;
          gap: 16px;
          transition:
            transform 0.2s,
            border-color 0.2s,
            box-shadow 0.2s;
          animation: slideUp 0.6s ease-out;
          animation-fill-mode: both;
        }

        .stat-card:nth-child(1) {
          animation-delay: 0.1s;
        }
        .stat-card:nth-child(2) {
          animation-delay: 0.2s;
        }
        .stat-card:nth-child(3) {
          animation-delay: 0.3s;
        }
        .stat-card:nth-child(4) {
          animation-delay: 0.4s;
        }

        @keyframes slideUp {
          from {
            opacity: 0;
            transform: translateY(30px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .stat-card:hover {
          transform: translateY(-4px);
          border-color: color-mix(in srgb, var(--accent-soft) 30%, transparent);
          box-shadow: var(--shadow-md);
        }

        .stat-icon {
          width: 56px;
          height: 56px;
          border-radius: var(--radius-lg);
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--bg-subtle);
          color: var(--text-secondary);
        }

        .stat-content {
          flex: 1;
        }

        .stat-label {
          font-size: 13px;
          color: var(--text-secondary);
          margin-bottom: 8px;
          font-weight: 500;
        }

        .stat-value {
          font-size: 28px;
          font-weight: 700;
          color: var(--text);
          font-variant-numeric: tabular-nums;
        }

        /* Bots Section */
        .bots-section {
          margin-bottom: 40px;
        }

        .section-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
        }

        .section-header h2 {
          font-size: 24px;
          font-weight: 700;
        }

        .btn-text {
          display: flex;
          align-items: center;
          gap: 4px;
          background: none;
          border: none;
          color: var(--accent-soft);
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: color 0.2s;
        }

        .btn-text:hover {
          color: var(--accent-softer);
          gap: 8px;
        }

        .bots-list {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .bot-card {
          background: var(--bg-card);
          border: 1px solid var(--border-subtle);
          border-radius: var(--radius-xl);
          padding: 24px;
          transition:
            border-color 0.2s,
            transform 0.2s;
        }

        .bot-card:hover {
          border-color: color-mix(in srgb, var(--accent-soft) 30%, transparent);
          transform: translateX(4px);
        }

        .bot-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 16px;
        }

        .bot-info {
          display: flex;
          align-items: flex-start;
          gap: 12px;
        }

        .bot-info h3 {
          font-size: 18px;
          font-weight: 600;
          margin-bottom: 4px;
        }

        .bot-meta {
          display: flex;
          flex-wrap: wrap;
          gap: 4px;
          font-size: 13px;
          color: var(--text-secondary);
        }

        /* Параметры бота — отдельными метками, без символов-разделителей */
        .bot-meta > span {
          padding: 1px 8px;
          border: 1px solid var(--border);
          border-radius: var(--radius-md);
        }

        .bot-actions {
          display: flex;
          gap: 8px;
        }

        .btn-icon-small {
          padding: 8px;
          background: var(--bg-subtle);
          border: 1px solid var(--border);
          border-radius: var(--radius-md);
          color: var(--text-secondary);
          cursor: pointer;
          transition:
            background-color 0.2s,
            color 0.2s,
            opacity 0.2s;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .btn-icon-small:hover {
          background: var(--bg-hover);
          color: var(--text);
        }

        .bot-stats {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .bot-stat {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .bot-stat-label {
          font-size: 12px;
          color: var(--text-secondary);
        }

        .bot-stat-value {
          font-size: 20px;
          font-weight: 700;
          font-variant-numeric: tabular-nums;
        }

        .btn-bot-details {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 16px;
          background: color-mix(in srgb, var(--accent-soft) 10%, transparent);
          border: 1px solid
            color-mix(in srgb, var(--accent-soft) 20%, transparent);
          border-radius: var(--radius-md);
          color: var(--accent-soft);
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          transition:
            background-color 0.2s,
            transform 0.2s;
        }

        .btn-bot-details:hover {
          background: color-mix(in srgb, var(--accent-soft) 20%, transparent);
          transform: translateY(-1px);
        }

        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center; /* центрирует всё по горизонтали */
          padding: 80px 40px;
          background: var(--bg-card);
          border: 2px dashed var(--border);
          border-radius: var(--radius-xl);
          color: var(--text-secondary);
        }

        .empty-state svg {
          opacity: 0.3;
          margin-bottom: 24px;
        }

        .empty-state h3 {
          font-size: 20px;
          font-weight: 600;
          margin-bottom: 8px;
          color: var(--text);
        }

        .empty-state p {
          margin-bottom: 24px;
          font-size: 15px;
        }

        /* Quick Actions */
        .quick-actions {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 16px;
        }

        .action-card {
          display: flex;
          align-items: center;
          gap: 16px;
          padding: 20px;
          background: var(--bg-card);
          border: 1px solid var(--border-subtle);
          border-radius: var(--radius-xl);
          cursor: pointer;
          transition:
            background-color 0.2s,
            border-color 0.2s,
            transform 0.2s;
          text-align: left;
          color: inherit;
        }

        .action-card:hover {
          background: var(--bg-elevated);
          border-color: color-mix(in srgb, var(--accent-soft) 30%, transparent);
          transform: translateY(-2px);
        }

        .action-card svg:first-child {
          color: var(--accent-soft);
          flex-shrink: 0;
        }

        .action-card div {
          flex: 1;
        }

        .action-card h3 {
          font-size: 16px;
          font-weight: 600;
          margin-bottom: 4px;
        }

        .action-card p {
          font-size: 13px;
          color: var(--text-secondary);
        }

        .action-card svg:last-child {
          color: var(--text-secondary);
          flex-shrink: 0;
        }

        /* Modal */
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: var(--overlay);
          backdrop-filter: blur(4px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: var(--z-modal);
          animation: fadeIn 0.2s ease-out;
        }

        .modal-content {
          background: var(--bg-elevated);
          border: 1px solid var(--border);
          border-radius: var(--radius-xl);
          padding: 32px;
          max-width: 480px;
          width: 90%;
          animation: slideUp 0.3s ease-out;
        }

        .modal-content h2 {
          font-size: 24px;
          margin-bottom: 8px;
        }

        .modal-description {
          color: var(--text-secondary);
          margin-bottom: 24px;
          font-size: 14px;
        }

        .topup-amounts {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
          margin-bottom: 24px;
        }

        .amount-btn {
          padding: 16px;
          background: var(--bg-subtle);
          border: 1px solid var(--border);
          border-radius: var(--radius-lg);
          color: var(--text);
          font-size: 18px;
          font-weight: 600;
          cursor: pointer;
          transition:
            background-color 0.2s,
            border-color 0.2s,
            color 0.2s;
          font-variant-numeric: tabular-nums;
        }

        .amount-btn:hover {
          background: var(--bg-hover);
          border-color: color-mix(in srgb, var(--accent-soft) 30%, transparent);
        }

        .amount-btn.recommended {
          background: color-mix(in srgb, var(--accent) 15%, transparent);
          border-color: color-mix(in srgb, var(--accent) 30%, transparent);
          color: var(--accent-soft);
          position: relative;
        }

        .amount-btn.recommended::after {
          content: 'Рекомендуем';
          position: absolute;
          top: -8px;
          right: -8px;
          background: var(--accent);
          color: var(--text-on-accent);
          font-size: 10px;
          padding: 2px 8px;
          border-radius: var(--radius-sm);
          font-weight: 700;
        }

        .custom-amount {
          margin-bottom: 24px;
        }

        .custom-amount label {
          display: block;
          font-size: 14px;
          color: var(--text-secondary);
          margin-bottom: 8px;
        }

        .custom-amount input {
          width: 100%;
          padding: 16px;
          background: var(--bg-subtle);
          border: 1px solid var(--border);
          border-radius: var(--radius-lg);
          color: var(--text);
          font-size: 16px;
          font-weight: 600;
        }

        .custom-amount input:focus-visible {
          outline: none;
          border-color: color-mix(in srgb, var(--accent-soft) 50%, transparent);
          box-shadow: var(--ring);
        }

        .modal-actions {
          display: flex;
          gap: 12px;
        }

        .modal-actions .btn-primary,
        .modal-actions .btn-secondary {
          flex: 1;
          justify-content: center;
        }

        /* Loading / Error states for bots */
        .bots-loading,
        .bots-error {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 12px;
          padding: 60px 20px;
          background: var(--bg-card);
          border: 1px solid var(--border-subtle);
          border-radius: var(--radius-xl);
          color: var(--text-secondary);
          font-size: 15px;
        }

        .bots-error {
          color: var(--danger);
          border-color: color-mix(
            in srgb,
            var(--danger-strong) 20%,
            transparent
          );
        }

        .spin {
          animation: spin 1s linear infinite;
        }

        /* @keyframes spin — в globals.css */

        /* Bot card подсветка по статусу */
        .bot-card.status-error {
          border-color: color-mix(
            in srgb,
            var(--danger-strong) 20%,
            transparent
          );
        }

        .bot-title-block {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .bot-title-row {
          display: flex;
          align-items: center;
          gap: 8px;
          flex-wrap: wrap;
        }

        /* Бэйджи (DEMO и т.п.) */
        .badge {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 2px 8px;
          border-radius: var(--radius-md);
          font-size: 10px;
          font-weight: 700;
          letter-spacing: 0.5px;
          text-transform: uppercase;
        }

        .badge-dry {
          background: color-mix(in srgb, var(--accent-soft) 15%, transparent);
          color: var(--accent-soft);
          border: 1px solid
            color-mix(in srgb, var(--accent-soft) 30%, transparent);
        }

        /* Status row под заголовком карточки */
        .bot-status-row {
          display: flex;
          align-items: center;
          gap: 8px;
          margin: 12px 0 16px;
          padding: 8px 12px;
          border-radius: var(--radius-md);
          font-size: 13px;
          font-weight: 500;
          background: var(--bg-subtle);
        }

        .bot-status-row.status-running {
          color: var(--success);
        }
        .bot-status-row.status-starting {
          color: var(--warning);
        }
        .bot-status-row.status-stopped,
        .bot-status-row.status-created {
          color: var(--text-secondary);
        }
        .bot-status-row.status-error {
          color: var(--danger);
          background: color-mix(in srgb, var(--danger-strong) 10%, transparent);
        }

        .status-error-msg {
          color: var(--danger);
          opacity: 0.85;
          font-weight: 400;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          max-width: 60%;
        }

        /* Кнопки действий */
        .btn-icon-small:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .btn-icon-danger:hover:not(:disabled) {
          background: color-mix(
            in srgb,
            var(--danger-strong) 15%,
            transparent
          ) !important;
          color: var(--danger) !important;
        }

        /* Кнопка удаления в модалке */
        .btn-danger {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          padding: 12px 20px;
          background: var(--danger-strong);
          color: var(--text-on-accent);
          border: none;
          border-radius: var(--radius-lg);
          font-size: 15px;
          font-weight: 600;
          cursor: pointer;
          transition:
            background-color 0.2s,
            transform 0.2s,
            opacity 0.2s;
          flex: 1;
        }
        .btn-danger:hover:not(:disabled) {
          background: color-mix(in srgb, var(--danger-strong) 85%, black);
          transform: translateY(-1px);
        }
        .btn-danger:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .btn-text:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        @media (max-width: 768px) {
          .dashboard-header {
            flex-direction: column;
            gap: 16px;
            padding: 16px 20px;
          }

          .header-left {
            width: 100%;
            flex-direction: column;
            gap: 16px;
          }

          .header-right {
            width: 100%;
            justify-content: space-between;
          }

          .home-hero-section {
            flex-direction: column;
            gap: 20px;
            text-align: center;
          }

          .home-hero-actions {
            width: 100%;
            flex-direction: column;
          }

          .stats-grid {
            grid-template-columns: 1fr;
          }

          .low-balance-banner {
            flex-direction: column;
            gap: 8px;
            padding: 16px;
          }

          .dashboard-main {
            padding: 20px;
          }

          .amount-btn.selected {
            background: color-mix(in srgb, var(--accent-soft) 20%, transparent);
            border-color: color-mix(
              in srgb,
              var(--accent-soft) 60%,
              transparent
            );
            color: var(--accent-soft);
          }
        }
      `}</style>
    </div>
  );
};

export default TradingBotDashboard;
