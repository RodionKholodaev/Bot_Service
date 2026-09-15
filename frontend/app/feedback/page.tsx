'use client';
import React, { useState, useEffect, useCallback } from 'react';
import { BrandMark } from '@/app/components/BrandMark';
import {
  Settings,
  CreditCard,
  MessageSquare,
  Send,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Star,
  Lightbulb,
  Bug,
  MousePointerClick,
  MessageCircle,
  type LucideIcon,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { SiteFooter } from '@/app/components/SiteFooter';
import { apiFetch } from '@/lib/api';

// Запросы идут через apiFetch (lib/api.ts): он же подставляет токен и он же
// сбрасывает сессию на 401.

// ── Темы обращения ────────────────────────────────────────
type TopicKey = 'idea' | 'bug' | 'ux' | 'other';

const TOPICS: { key: TopicKey; label: string; icon: LucideIcon }[] = [
  { key: 'idea', label: 'Идея / предложение', icon: Lightbulb },
  { key: 'bug', label: 'Нашёл(-а) баг', icon: Bug },
  { key: 'ux', label: 'Неудобно пользоваться', icon: MousePointerClick },
  { key: 'other', label: 'Другое', icon: MessageCircle },
];

const MESSAGE_MAX = 2000;
const MESSAGE_MIN = 10;

const FeedbackPage = () => {
  const router = useRouter();

  const [topic, setTopic] = useState<TopicKey | null>(null);
  const [message, setMessage] = useState('');
  const [email, setEmail] = useState('');
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);

  const [status, setStatus] = useState<
    'idle' | 'loading' | 'success' | 'error'
  >('idle');
  const [errorText, setErrorText] = useState('');

  const [serviceBalance, setServiceBalance] = useState<number>(0);

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

  useEffect(() => {
    if (!localStorage.getItem('access_token')) return;
    // Обычная загрузка данных при монтировании: setState происходит уже после
    // await внутри fetchBalance, каскадного ререндера нет. Правило этого
    // не различает и ругается на любой вызов функции с setState внутри.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchBalance();
  }, [fetchBalance]);

  // тот же светофор баланса, что и на главной
  const getBalanceStatus = (balance: number) => {
    if (balance < 100) return 'critical';
    if (balance < 1000) return 'low';
    return 'good';
  };
  const balanceStatus = getBalanceStatus(serviceBalance);

  const trimmed = message.trim();
  const canSubmit =
    topic !== null && trimmed.length >= MESSAGE_MIN && status !== 'loading';

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setStatus('loading');
    setErrorText('');
    try {
      await apiFetch('/feedback', {
        method: 'POST',
        body: {
          topic,
          message: trimmed,
          email: email.trim() || null,
          rating: rating || null,
        },
      });
      setStatus('success');
    } catch (e) {
      setErrorText(
        e instanceof Error ? e.message : 'Не удалось отправить отзыв',
      );
      setStatus('error');
    }
  };

  const resetForm = () => {
    setStatus('idle');
    setTopic(null);
    setMessage('');
    setEmail('');
    setRating(0);
  };

  return (
    <div className="dashboard-container">
      {/* Header — тот же, что на главной */}
      <header className="dashboard-header">
        <div className="header-left">
          <div className="logo">
            <BrandMark size={28} />
            <span>Rudder</span>
          </div>
          <nav className="main-nav">
            {/* span внутри Link обязателен: styled-jsx не скоупит классы на React-компоненты */}
            <Link href="/home">
              <span className="nav-item">Главная</span>
            </Link>
            <Link href="/stats">
              <span className="nav-item">Статистика</span>
            </Link>
            <Link href="/feedback">
              <span className="nav-item active">Обратная связь</span>
            </Link>
            <Link href="/guides">
              <span className="nav-item">Обучение</span>
            </Link>
          </nav>
        </div>
        <div className="header-right">
          <div className={`balance-indicator ${balanceStatus}`}>
            <CreditCard size={16} />
            <span className="balance-amount">
              {serviceBalance.toLocaleString('ru-RU')} ₽
            </span>
          </div>
          <Link href="/settings">
            <button className="btn-icon">
              <Settings size={20} />
            </button>
          </Link>
        </div>
      </header>

      {/* Main Content */}
      <div className="dashboard-scroll">
        <main className="dashboard-main">
          {/* Hero */}
          <section className="feedback-hero">
            <span className="hero-badge">
              <span className="hero-badge-icon">
                <MessageSquare size={14} />
              </span>
              Обратная связь
            </span>
            <h1>Нам важно ваше мнение</h1>
            <p>
              Мы правда рады любым предложениям и конструктивной критике — они
              помогают делать Rudder лучше. Расскажите, что понравилось, что
              стоит поправить, или чего не хватает.
            </p>
          </section>

          {/* Форма */}
          <section className="feedback-card">
            {status === 'success' ? (
              <div className="success-state">
                <div className="success-icon">
                  <CheckCircle2 size={56} />
                </div>
                <h2>Спасибо! Сообщение отправлено</h2>
                <p>
                  Мы читаем каждый отзыв и стараемся отвечать в течение 1–2
                  дней.
                </p>
                <div className="success-actions">
                  <button className="btn-secondary" onClick={resetForm}>
                    Написать ещё
                  </button>
                  <Link href="/home">
                    <button className="btn-primary">
                      Вернуться на главную
                    </button>
                  </Link>
                </div>
              </div>
            ) : (
              <>
                {/* Тема обращения */}
                <div className="field">
                  <label className="field-label">Тема обращения</label>
                  <div className="topic-row">
                    {TOPICS.map((t) => (
                      <button
                        key={t.key}
                        type="button"
                        className={`topic-chip ${topic === t.key ? 'active' : ''}`}
                        onClick={() => setTopic(t.key)}
                      >
                        <span className="topic-icon">
                          <t.icon size={16} aria-hidden="true" />
                        </span>
                        {t.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Сообщение */}
                <div className="field">
                  <label className="field-label" htmlFor="fb-message">
                    Ваше сообщение
                  </label>
                  <textarea
                    id="fb-message"
                    className="field-textarea"
                    placeholder="Опишите идею, проблему или что угодно ещё — мы читаем каждое сообщение"
                    value={message}
                    maxLength={MESSAGE_MAX}
                    onChange={(e) => setMessage(e.target.value)}
                  />
                  <div className="field-footer">
                    <span className="field-hint">
                      {trimmed.length > 0 && trimmed.length < MESSAGE_MIN
                        ? `Ещё хотя бы ${MESSAGE_MIN - trimmed.length} символов`
                        : ''}
                    </span>
                    <span className="char-count">
                      {message.length} / {MESSAGE_MAX}
                    </span>
                  </div>
                </div>

                {/* Email + оценка */}
                <div className="field-grid">
                  <div className="field">
                    <label className="field-label" htmlFor="fb-email">
                      Email{' '}
                      <span className="field-optional">(необязательно)</span>
                    </label>
                    <input
                      id="fb-email"
                      className="field-input"
                      type="email"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                    />
                    <div className="field-footer">
                      <span className="field-hint">
                        Оставьте, если хотите получить ответ
                      </span>
                    </div>
                  </div>

                  <div className="field">
                    <label className="field-label">
                      Насколько вам нравится сервис?{' '}
                      <span className="field-optional">(необязательно)</span>
                    </label>
                    <div
                      className="stars"
                      onMouseLeave={() => setHoverRating(0)}
                    >
                      {[1, 2, 3, 4, 5].map((n) => {
                        const shown = hoverRating || rating;
                        const active = n <= shown;
                        return (
                          <button
                            key={n}
                            type="button"
                            className={`star-btn ${active ? 'active' : ''}`}
                            onClick={() => setRating(n === rating ? 0 : n)}
                            onMouseEnter={() => setHoverRating(n)}
                            aria-label={`Оценка ${n} из 5`}
                          >
                            {/* SVG-атрибуты не читают CSS-переменные:
                                #fbbf24 — это --warning, #4b5563 — --text-dim */}
                            <Star
                              size={26}
                              fill={active ? '#fbbf24' : 'none'}
                              color={active ? '#fbbf24' : '#4b5563'}
                            />
                          </button>
                        );
                      })}
                      <span className="stars-value">
                        {rating > 0 ? `${rating} / 5` : ''}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Ошибка */}
                {status === 'error' && (
                  <div className="form-error">
                    <span className="error-icon">
                      <AlertCircle size={16} />
                    </span>
                    <span>{errorText}</span>
                  </div>
                )}

                {/* Отправка */}
                <button
                  className="btn-primary submit-btn"
                  onClick={handleSubmit}
                  disabled={!canSubmit}
                >
                  {status === 'loading' ? (
                    <>
                      <span className="spin">
                        <Loader2 size={18} />
                      </span>
                      Отправляем...
                    </>
                  ) : (
                    <>
                      <Send size={18} />
                      Отправить отзыв
                    </>
                  )}
                </button>
              </>
            )}
          </section>

          <p className="feedback-footnote">
            Срочный вопрос по боту или деньгам?{' '}
            <a
              href="https://t.me/Rodion137"
              target="_blank"
              rel="noopener noreferrer"
            >
              Напишите в поддержку
            </a>
          </p>
          <SiteFooter />
        </main>
      </div>

      <style jsx>{`
        * {
          margin: 0;
          padding: 0;
          box-sizing: border-box;
        }

        .dashboard-container {
          height: 100vh;
          display: flex;
          flex-direction: column;
          overflow: hidden;
          background: var(--bg-page);
          color: var(--text);
        }

        /* ── Header (как на главной) ─────────────── */
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
          gap: 10px;
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
          border-radius: 8px;
          font-size: 14px;
          font-weight: 500;
          transition: all 0.2s;
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
          padding: 10px 18px;
          border-radius: 12px;
          font-weight: 600;
          font-size: 15px;
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
        }

        .btn-icon {
          padding: 10px;
          background: var(--bg-subtle);
          border: 1px solid var(--border);
          border-radius: 10px;
          color: var(--text-secondary);
          cursor: pointer;
          transition: all 0.2s;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .btn-icon:hover {
          background: var(--bg-hover);
          color: var(--text);
          transform: translateY(-1px);
        }

        /* ── Scroll area (как на главной) ────────── */
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
          border-radius: 4px;
        }

        .dashboard-scroll::-webkit-scrollbar-thumb:hover {
          background: var(--scrollbar-thumb-hover);
        }

        .dashboard-main {
          padding: 40px;
          max-width: 900px;
          margin: 0 auto;
        }

        /* ── Hero ────────────────────────────────── */
        .feedback-hero {
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
          padding: 24px 0 44px;
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

        .hero-badge {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 7px 16px;
          margin-bottom: 22px;
          background: color-mix(in srgb, var(--accent-soft) 10%, transparent);
          border: 1px solid
            color-mix(in srgb, var(--accent-soft) 20%, transparent);
          border-radius: 999px;
          color: var(--accent-soft);
          font-size: 13px;
          font-weight: 600;
        }

        .hero-badge-icon {
          display: inline-flex;
          color: var(--accent-soft);
        }

        .feedback-hero h1 {
          font-size: 38px;
          font-weight: 800;
          line-height: 1.25;
          margin-bottom: 16px;
          color: var(--text);
        }

        .feedback-hero p {
          color: var(--text-secondary);
          font-size: 16px;
          line-height: 1.6;
          max-width: 620px;
        }

        /* ── Buttons ─────────────────────────────── */
        .btn-primary,
        .btn-secondary {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 12px 24px;
          border-radius: 12px;
          font-weight: 600;
          font-size: 15px;
          cursor: pointer;
          transition: all 0.3s;
          border: none;
          font-family: inherit;
        }

        .btn-primary {
          background: var(--accent);
          color: var(--text-on-accent);
          box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
        }

        .btn-primary:hover:not(:disabled) {
          background: var(--accent-hover);
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
        }

        .btn-primary:disabled {
          background: var(--bg-hover);
          color: var(--text-muted);
          box-shadow: none;
          cursor: not-allowed;
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

        /* ── Card ────────────────────────────────── */
        .feedback-card {
          display: flex;
          flex-direction: column;
          gap: 26px;
          background: var(--bg-card);
          border: 1px solid var(--border-subtle);
          border-radius: 20px;
          padding: 32px;
          animation: slideUp 0.6s ease-out 0.1s both;
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

        /* ── Fields ──────────────────────────────── */
        .field {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .field-label {
          font-size: 14px;
          font-weight: 600;
          color: var(--text);
        }

        .field-optional {
          color: var(--text-muted);
          font-weight: 500;
        }

        .field-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 12px;
          min-height: 16px;
        }

        .field-hint {
          font-size: 12px;
          color: var(--text-muted);
        }

        .char-count {
          font-size: 12px;
          color: var(--text-dim);
          margin-left: auto;
        }

        .field-input,
        .field-textarea {
          width: 100%;
          padding: 14px 16px;
          background: var(--bg-subtle);
          border: 1.5px solid var(--border);
          border-radius: 12px;
          color: var(--text);
          font-size: 15px;
          font-family: inherit;
          transition: all 0.2s;
        }

        .field-textarea {
          min-height: 150px;
          line-height: 1.6;
          resize: vertical;
        }

        .field-input::placeholder,
        .field-textarea::placeholder {
          color: var(--text-dim);
        }

        .field-input:focus,
        .field-textarea:focus {
          outline: none;
          border-color: color-mix(in srgb, var(--accent-soft) 50%, transparent);
          background: color-mix(in srgb, var(--accent-soft) 5%, transparent);
          box-shadow: 0 0 0 3px
            color-mix(in srgb, var(--accent-soft) 10%, transparent);
        }

        .field-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 20px;
          align-items: start;
        }

        /* ── Topic chips ─────────────────────────── */
        .topic-row {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
        }

        .topic-chip {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 10px 16px;
          background: var(--bg-subtle);
          border: 1.5px solid var(--border);
          border-radius: 12px;
          color: var(--text-secondary);
          font-size: 14px;
          font-weight: 500;
          font-family: inherit;
          cursor: pointer;
          transition: all 0.2s;
        }

        .topic-chip:hover {
          background: color-mix(in srgb, var(--accent-soft) 5%, transparent);
          border-color: color-mix(in srgb, var(--accent-soft) 20%, transparent);
          color: var(--text);
          transform: translateY(-1px);
        }

        .topic-chip.active {
          background: color-mix(in srgb, var(--accent-soft) 10%, transparent);
          border-color: color-mix(in srgb, var(--accent-soft) 50%, transparent);
          color: var(--accent-soft);
        }

        .topic-icon {
          display: inline-flex;
        }

        /* ── Stars ───────────────────────────────── */
        .stars {
          display: flex;
          align-items: center;
          gap: 4px;
          height: 52px;
        }

        .star-btn {
          background: none;
          border: none;
          padding: 2px;
          line-height: 0;
          cursor: pointer;
          transition: transform 0.15s;
        }

        .star-btn:hover {
          transform: scale(1.15);
        }

        .stars-value {
          margin-left: 10px;
          font-size: 13px;
          font-weight: 600;
          color: var(--warning);
        }

        /* ── Error ───────────────────────────────── */
        .form-error {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 12px 16px;
          background: color-mix(in srgb, var(--danger-strong) 10%, transparent);
          border: 1px solid
            color-mix(in srgb, var(--danger-strong) 20%, transparent);
          border-radius: 10px;
          color: var(--danger);
          font-size: 14px;
        }

        .error-icon {
          display: inline-flex;
          flex-shrink: 0;
        }

        /* ── Submit ──────────────────────────────── */
        .submit-btn {
          width: 100%;
          justify-content: center;
          padding: 16px;
          font-size: 16px;
        }

        .spin {
          display: inline-flex;
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          from {
            transform: rotate(0deg);
          }
          to {
            transform: rotate(360deg);
          }
        }

        /* ── Success ─────────────────────────────── */
        .success-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
          gap: 14px;
          padding: 32px 20px;
        }

        .success-icon {
          color: var(--success);
          display: flex;
          align-items: center;
          justify-content: center;
          width: 88px;
          height: 88px;
          border-radius: 50%;
          background: color-mix(
            in srgb,
            var(--success-strong) 10%,
            transparent
          );
          border: 1px solid
            color-mix(in srgb, var(--success-strong) 30%, transparent);
          margin-bottom: 6px;
          animation: popIn 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }

        @keyframes popIn {
          from {
            transform: scale(0.5);
            opacity: 0;
          }
          to {
            transform: scale(1);
            opacity: 1;
          }
        }

        .success-state h2 {
          font-size: 22px;
          font-weight: 700;
          color: var(--text);
        }

        .success-state p {
          font-size: 15px;
          color: var(--text-secondary);
          line-height: 1.6;
          max-width: 420px;
        }

        .success-actions {
          display: flex;
          gap: 12px;
          margin-top: 10px;
          flex-wrap: wrap;
          justify-content: center;
        }

        /* ── Footnote ────────────────────────────── */
        .feedback-footnote {
          text-align: center;
          margin-top: 24px;
          font-size: 13px;
          color: var(--text-muted);
        }

        .feedback-footnote a {
          color: var(--accent-soft);
          text-decoration: none;
          font-weight: 600;
        }

        .feedback-footnote a:hover {
          color: var(--accent-softer);
        }

        /* ── Responsive ──────────────────────────── */
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

          .dashboard-main {
            padding: 20px;
          }

          .feedback-hero {
            padding: 8px 0 32px;
          }

          .feedback-hero h1 {
            font-size: 28px;
          }

          .feedback-hero p {
            font-size: 15px;
          }

          .field-grid {
            grid-template-columns: 1fr;
          }

          .feedback-card {
            padding: 22px;
          }

          .topic-chip {
            flex: 1 1 100%;
          }
        }
      `}</style>
    </div>
  );
};

export default FeedbackPage;
