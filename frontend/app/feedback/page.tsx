'use client';
import React, { useState, useEffect, useCallback } from 'react';
import {
  Zap,
  Settings,
  CreditCard,
  MessageSquare,
  Send,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Star,
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { SiteFooter } from '@/app/components/SiteFooter';

// Запросы идут через Next.js-прокси на /api/...
const API_BASE = '/api';

const getAuthHeader = (): Record<string, string> => {
  if (typeof window === 'undefined') return {};
  const token = localStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

// ── Темы обращения ────────────────────────────────────────
type TopicKey = 'idea' | 'bug' | 'ux' | 'other';

const TOPICS: { key: TopicKey; label: string; emoji: string }[] = [
  { key: 'idea', label: 'Идея / предложение', emoji: '💡' },
  { key: 'bug', label: 'Нашёл(-а) баг', emoji: '🐛' },
  { key: 'ux', label: 'Неудобно пользоваться', emoji: '🤔' },
  { key: 'other', label: 'Другое', emoji: '💬' },
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
      const res = await fetch(`${API_BASE}/users/me/balance`, {
        headers: { ...getAuthHeader() },
        cache: 'no-store',
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: { service_balance: number } = await res.json();
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
      const res = await fetch(`${API_BASE}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
        body: JSON.stringify({
          topic,
          message: trimmed,
          email: email.trim() || null,
          rating: rating || null,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail ?? `HTTP ${res.status}`);
      }
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
            <Zap size={28} />
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
                        <span className="topic-emoji">{t.emoji}</span>
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
          background: linear-gradient(135deg, #0a0e1a 0%, #1a1f35 100%);
          color: #e4e7f0;
          font-family:
            'SF Pro Display',
            -apple-system,
            BlinkMacSystemFont,
            'Segoe UI',
            sans-serif;
        }

        /* ── Header (как на главной) ─────────────── */
        .dashboard-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 20px 40px;
          background: rgba(26, 31, 53, 0.6);
          backdrop-filter: blur(20px);
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
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
          color: #60a5fa;
        }

        .main-nav {
          display: flex;
          gap: 8px;
        }

        .nav-item {
          padding: 8px 16px;
          color: #9ca3af;
          text-decoration: none;
          border-radius: 8px;
          font-size: 14px;
          font-weight: 500;
          transition: all 0.2s;
          display: inline-flex;
          align-items: center;
        }

        .nav-item:hover {
          color: #e4e7f0;
          background: rgba(255, 255, 255, 0.05);
        }

        .nav-item.active {
          color: #60a5fa;
          background: rgba(96, 165, 250, 0.1);
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
        }

        .balance-indicator.good {
          background: rgba(16, 185, 129, 0.1);
          border-color: rgba(16, 185, 129, 0.3);
          color: #34d399;
        }

        .balance-indicator.low {
          background: rgba(251, 191, 36, 0.1);
          border-color: rgba(251, 191, 36, 0.3);
          color: #fbbf24;
        }

        .balance-indicator.critical {
          background: rgba(239, 68, 68, 0.1);
          border-color: rgba(239, 68, 68, 0.4);
          color: #f87171;
        }

        .btn-icon {
          padding: 10px;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 10px;
          color: #9ca3af;
          cursor: pointer;
          transition: all 0.2s;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .btn-icon:hover {
          background: rgba(255, 255, 255, 0.1);
          color: #e4e7f0;
          transform: translateY(-1px);
        }

        /* ── Scroll area (как на главной) ────────── */
        .dashboard-scroll {
          flex: 1;
          overflow-y: auto;
          scrollbar-width: thin;
          scrollbar-color: rgba(156, 163, 175, 0.35) rgba(255, 255, 255, 0.05);
        }

        .dashboard-scroll::-webkit-scrollbar {
          width: 4px;
        }

        .dashboard-scroll::-webkit-scrollbar-track {
          background: rgba(255, 255, 255, 0.05);
        }

        .dashboard-scroll::-webkit-scrollbar-thumb {
          background: rgba(156, 163, 175, 0.35);
          border-radius: 4px;
        }

        .dashboard-scroll::-webkit-scrollbar-thumb:hover {
          background: rgba(156, 163, 175, 0.5);
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
          background: rgba(96, 165, 250, 0.12);
          border: 1px solid rgba(96, 165, 250, 0.25);
          border-radius: 999px;
          color: #8ab4ff;
          font-size: 13px;
          font-weight: 600;
        }

        .hero-badge-icon {
          display: inline-flex;
          color: #8ab4ff;
        }

        .feedback-hero h1 {
          font-size: 38px;
          font-weight: 800;
          line-height: 1.25;
          margin-bottom: 16px;
          background: linear-gradient(90deg, #c7d2fe 0%, #93c5fd 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }

        .feedback-hero p {
          color: #9ca3af;
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
          background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
          color: white;
          box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3);
        }

        .btn-primary:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 6px 20px rgba(59, 130, 246, 0.4);
        }

        .btn-primary:disabled {
          background: rgba(255, 255, 255, 0.06);
          color: #6b7280;
          box-shadow: none;
          cursor: not-allowed;
        }

        .btn-secondary {
          background: rgba(255, 255, 255, 0.05);
          color: #e4e7f0;
          border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .btn-secondary:hover {
          background: rgba(255, 255, 255, 0.1);
          transform: translateY(-2px);
        }

        /* ── Card ────────────────────────────────── */
        .feedback-card {
          display: flex;
          flex-direction: column;
          gap: 26px;
          background: rgba(26, 31, 53, 0.6);
          border: 1px solid rgba(255, 255, 255, 0.05);
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
          color: #c7cde0;
        }

        .field-optional {
          color: #6b7280;
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
          color: #6b7280;
        }

        .char-count {
          font-size: 12px;
          color: #4b5563;
          margin-left: auto;
        }

        .field-input,
        .field-textarea {
          width: 100%;
          padding: 14px 16px;
          background: rgba(255, 255, 255, 0.04);
          border: 1.5px solid rgba(255, 255, 255, 0.08);
          border-radius: 12px;
          color: #e4e7f0;
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
          color: #4b5563;
        }

        .field-input:focus,
        .field-textarea:focus {
          outline: none;
          border-color: rgba(96, 165, 250, 0.5);
          background: rgba(96, 165, 250, 0.04);
          box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.08);
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
          background: rgba(255, 255, 255, 0.03);
          border: 1.5px solid rgba(255, 255, 255, 0.08);
          border-radius: 12px;
          color: #9ca3af;
          font-size: 14px;
          font-weight: 500;
          font-family: inherit;
          cursor: pointer;
          transition: all 0.2s;
        }

        .topic-chip:hover {
          background: rgba(96, 165, 250, 0.06);
          border-color: rgba(96, 165, 250, 0.25);
          color: #c4d4f0;
          transform: translateY(-1px);
        }

        .topic-chip.active {
          background: rgba(96, 165, 250, 0.12);
          border-color: rgba(96, 165, 250, 0.5);
          color: #60a5fa;
        }

        .topic-emoji {
          font-size: 16px;
          line-height: 1;
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
          color: #fbbf24;
        }

        /* ── Error ───────────────────────────────── */
        .form-error {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 12px 16px;
          background: rgba(239, 68, 68, 0.08);
          border: 1px solid rgba(239, 68, 68, 0.2);
          border-radius: 10px;
          color: #fca5a5;
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
          color: #34d399;
          display: flex;
          align-items: center;
          justify-content: center;
          width: 88px;
          height: 88px;
          border-radius: 50%;
          background: rgba(16, 185, 129, 0.12);
          border: 1px solid rgba(16, 185, 129, 0.3);
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
          color: #e4e7f0;
        }

        .success-state p {
          font-size: 15px;
          color: #9ca3af;
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
          color: #6b7280;
        }

        .feedback-footnote a {
          color: #60a5fa;
          text-decoration: none;
          font-weight: 600;
        }

        .feedback-footnote a:hover {
          color: #93c5fd;
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
