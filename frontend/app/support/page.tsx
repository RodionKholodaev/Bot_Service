"use client"
import React, { useState } from 'react';
import { Zap, CreditCard, Settings, Plus, MessageCircle, ChevronLeft, Send, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import Link from 'next/link';

const API_BASE = '/api';

const getAuthHeader = (): Record<string, string> => {
  if (typeof window === 'undefined') return {};
  const token = localStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

type Category = 'technical' | 'billing' | 'bots' | 'other';

const CATEGORIES: { value: Category; label: string; emoji: string }[] = [
  { value: 'technical', label: 'Техническая проблема', emoji: '⚙️' },
  { value: 'billing',   label: 'Вопрос по оплате',    emoji: '💳' },
  { value: 'bots',      label: 'Работа ботов',         emoji: '🤖' },
  { value: 'other',     label: 'Другое',               emoji: '💬' },
];

const SupportPage = () => {
  const [name,     setName]     = useState('');
  const [email,    setEmail]    = useState('');
  const [category, setCategory] = useState<Category | ''>('');
  const [message,  setMessage]  = useState('');

  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [errorText, setErrorText] = useState('');

  const isValid = name.trim() && email.trim() && category && message.trim();

  const handleSubmit = async () => {
    if (!isValid || status === 'loading') return;
    setStatus('loading');
    setErrorText('');
    try {
      const res = await fetch(`${API_BASE}/support`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
        },
        body: JSON.stringify({ name, email, category, message }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail ?? `HTTP ${res.status}`);
      }
      setStatus('success');
    } catch (e) {
      setErrorText(e instanceof Error ? e.message : 'Не удалось отправить сообщение');
      setStatus('error');
    }
  };

  return (
    <div className="dashboard-container">
      {/* Header */}
      <header className="dashboard-header">
        <div className="header-left">
          <div className="logo">
            <Zap size={28} />
            <span>CryptoBot</span>
          </div>
          <nav className="main-nav">
            <Link href="/" className="nav-item">Главная</Link>
            <Link href="/stats" className="nav-item">Статистика</Link>
            <a href="#" className="nav-item">Обучение</a>
          </nav>
        </div>
        <div className="header-right">
          <Link href="/settings">
            <button className="btn-icon">
              <Settings size={20} />
            </button>
          </Link>
        </div>
      </header>

      {/* Main */}
      <main className="dashboard-main">
        {/* Hero */}
        <section className="home-hero-section">
          <div className="home-hero-content">
            <h1>Поддержка</h1>
            <p>Опишите проблему — мы ответим в течение нескольких часов</p>
          </div>
          <div className="home-hero-actions">
            <Link href="/">
              <button className="btn-secondary">
                <ChevronLeft size={20} />
                Назад
              </button>
            </Link>
          </div>
        </section>

        <div className="support-layout">
          {/* Form card */}
          <div className="support-card">
            <div className="support-card-header">
              <MessageCircle size={22} className="card-header-icon" />
              <h2>Написать в поддержку</h2>
            </div>

            {status === 'success' ? (
              <div className="success-state">
                <div className="success-icon-wrap">
                  <CheckCircle size={52} />
                </div>
                <h3>Сообщение отправлено!</h3>
                <p>Мы получили ваш запрос и ответим на почту в ближайшее время.</p>
                <button
                  className="btn-primary"
                  onClick={() => {
                    setStatus('idle');
                    setName(''); setEmail(''); setCategory(''); setMessage('');
                  }}
                >
                  Отправить ещё одно
                </button>
              </div>
            ) : (
              <div className="form-body">
                {/* Name + Email */}
                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Ваше имя</label>
                    <input
                      className="form-input"
                      type="text"
                      placeholder="Иван Иванов"
                      value={name}
                      onChange={e => setName(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Email для ответа</label>
                    <input
                      className="form-input"
                      type="email"
                      placeholder="you@example.com"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                    />
                  </div>
                </div>

                {/* Category */}
                <div className="form-group">
                  <label className="form-label">Тема обращения</label>
                  <div className="category-grid">
                    {CATEGORIES.map(c => (
                      <button
                        key={c.value}
                        className={`category-btn ${category === c.value ? 'active' : ''}`}
                        onClick={() => setCategory(c.value)}
                      >
                        <span className="cat-emoji">{c.emoji}</span>
                        <span>{c.label}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Message */}
                <div className="form-group">
                  <label className="form-label">Сообщение</label>
                  <textarea
                    className="form-textarea"
                    placeholder="Опишите вашу проблему как можно подробнее..."
                    value={message}
                    onChange={e => setMessage(e.target.value)}
                    rows={6}
                  />
                  <div className="char-count">{message.length} / 2000</div>
                </div>

                {/* Error */}
                {status === 'error' && (
                  <div className="form-error">
                    <AlertCircle size={16} />
                    <span>{errorText}</span>
                  </div>
                )}

                {/* Submit */}
                <button
                  className="btn-primary submit-btn"
                  onClick={handleSubmit}
                  disabled={!isValid || status === 'loading'}
                >
                  {status === 'loading' ? (
                    <><Loader2 size={18} className="spin" /> Отправляем...</>
                  ) : (
                    <><Send size={18} /> Отправить сообщение</>
                  )}
                </button>
              </div>
            )}
          </div>

          {/* Sidebar info */}
          <div className="support-sidebar">
            <div className="info-card">
              <h3>⏱ Время ответа</h3>
              <p>Обычно отвечаем в течение <strong>2–4 часов</strong> в рабочее время.</p>
            </div>
            <div className="info-card">
              <h3>📋 Что указать</h3>
              <ul className="info-list">
                <li>Название бота и торговую пару</li>
                <li>Что именно пошло не так</li>
                <li>Скриншот ошибки (если есть)</li>
              </ul>
            </div>
            <div className="info-card highlight">
              <h3>🚨 Срочный вопрос?</h3>
              <p>Если боты не работают и вы теряете деньги — напишите напрямую в Telegram.</p>
              <a href="https://t.me/cryptobot_support" target="_blank" rel="noopener noreferrer" className="tg-btn">
                Написать в Telegram
              </a>
            </div>
          </div>
        </div>
      </main>

      <style jsx>{`
        * { margin: 0; padding: 0; box-sizing: border-box; }

        .dashboard-container {
          min-height: 100vh;
          background: linear-gradient(135deg, #0a0e1a 0%, #1a1f35 100%);
          color: #e4e7f0;
          font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        }

        /* ── Header ───────────────────────────────── */
        .dashboard-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 20px 40px;
          background: rgba(26, 31, 53, 0.6);
          backdrop-filter: blur(20px);
          border-bottom: 1px solid rgba(255,255,255,0.05);
          position: sticky;
          top: 0;
          z-index: 100;
        }
        .header-left { display: flex; align-items: center; gap: 48px; }
        .logo { display: flex; align-items: center; gap: 10px; font-size: 22px; font-weight: 700; color: #60a5fa; }
        .main-nav { display: flex; gap: 8px; }
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
        .nav-item:hover { color: #e4e7f0; background: rgba(255,255,255,0.05); }
        .nav-item.active { color: #60a5fa; background: rgba(96,165,250,0.1); }
        .header-right { display: flex; align-items: center; gap: 12px; }
        .btn-icon {
          padding: 10px;
          background: rgba(255,255,255,0.05);
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 10px;
          color: #9ca3af;
          cursor: pointer;
          transition: all 0.2s;
          display: flex; align-items: center; justify-content: center;
        }
        .btn-icon:hover { background: rgba(255,255,255,0.1); color: #e4e7f0; transform: translateY(-1px); }

        /* ── Main ────────────────────────────────── */
        .dashboard-main { padding: 40px; max-width: 1200px; margin: 0 auto; }

        /* ── Hero ────────────────────────────────── */
        .home-hero-section {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 40px;
          padding: 32px;
          background: linear-gradient(135deg, rgba(59,130,246,0.1) 0%, rgba(147,51,234,0.1) 100%);
          border-radius: 20px;
          border: 1px solid rgba(96,165,250,0.2);
          animation: fadeIn 0.6s ease-out;
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(20px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .home-hero-content h1 {
          font-size: 32px;
          font-weight: 700;
          margin-bottom: 8px;
          background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }
        .home-hero-content p { color: #9ca3af; font-size: 16px; }
        .home-hero-actions { display: flex; gap: 12px; }

        /* ── Buttons ─────────────────────────────── */
        .btn-primary, .btn-secondary {
          display: flex; align-items: center; gap: 8px;
          padding: 12px 24px; border-radius: 12px;
          font-weight: 600; font-size: 15px;
          cursor: pointer; transition: all 0.3s; border: none;
        }
        .btn-primary {
          background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
          color: white;
          box-shadow: 0 4px 15px rgba(59,130,246,0.3);
        }
        .btn-primary:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(59,130,246,0.4); }
        .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-secondary {
          background: rgba(255,255,255,0.05);
          color: #e4e7f0;
          border: 1px solid rgba(255,255,255,0.1);
        }
        .btn-secondary:hover { background: rgba(255,255,255,0.1); transform: translateY(-2px); }

        /* ── Layout ──────────────────────────────── */
        .support-layout {
          display: grid;
          grid-template-columns: 1fr 300px;
          gap: 24px;
          align-items: start;
        }

        /* ── Form Card ───────────────────────────── */
        .support-card {
          background: rgba(26,31,53,0.6);
          border: 1px solid rgba(255,255,255,0.05);
          border-radius: 20px;
          padding: 32px;
          animation: fadeIn 0.5s ease-out 0.1s both;
        }
        .support-card-header {
          display: flex;
          align-items: center;
          gap: 12px;
          margin-bottom: 28px;
          padding-bottom: 20px;
          border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .support-card-header h2 { font-size: 20px; font-weight: 700; color: #e4e7f0; }
        .card-header-icon { color: #60a5fa; flex-shrink: 0; }

        /* ── Form ────────────────────────────────── */
        .form-body { display: flex; flex-direction: column; gap: 24px; }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .form-group { display: flex; flex-direction: column; gap: 8px; }
        .form-label { font-size: 13px; font-weight: 600; color: #9ca3af; letter-spacing: 0.3px; }

        .form-input, .form-textarea {
          width: 100%;
          padding: 14px 16px;
          background: rgba(255,255,255,0.04);
          border: 1.5px solid rgba(255,255,255,0.08);
          border-radius: 12px;
          color: #e4e7f0;
          font-size: 15px;
          font-family: inherit;
          transition: all 0.2s;
          resize: none;
        }
        .form-input::placeholder, .form-textarea::placeholder { color: #4b5563; }
        .form-input:focus, .form-textarea:focus {
          outline: none;
          border-color: rgba(96,165,250,0.5);
          background: rgba(96,165,250,0.04);
          box-shadow: 0 0 0 3px rgba(96,165,250,0.08);
        }

        /* ── Category grid ───────────────────────── */
        .category-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 10px;
        }
        .category-btn {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 14px 16px;
          background: rgba(255,255,255,0.03);
          border: 1.5px solid rgba(255,255,255,0.07);
          border-radius: 12px;
          color: #9ca3af;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
          text-align: left;
        }
        .category-btn:hover {
          background: rgba(96,165,250,0.06);
          border-color: rgba(96,165,250,0.25);
          color: #c4d4f0;
        }
        .category-btn.active {
          background: rgba(96,165,250,0.12);
          border-color: rgba(96,165,250,0.5);
          color: #60a5fa;
        }
        .cat-emoji { font-size: 18px; line-height: 1; }

        /* ── Char count ──────────────────────────── */
        .char-count { font-size: 12px; color: #4b5563; text-align: right; margin-top: 4px; }

        /* ── Error ───────────────────────────────── */
        .form-error {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 12px 16px;
          background: rgba(239,68,68,0.08);
          border: 1px solid rgba(239,68,68,0.2);
          border-radius: 10px;
          color: #fca5a5;
          font-size: 14px;
        }

        /* ── Submit button ───────────────────────── */
        .submit-btn { width: 100%; justify-content: center; padding: 16px; font-size: 16px; }

        /* ── Success state ───────────────────────── */
        .success-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
          padding: 40px 20px;
          gap: 16px;
        }
        .success-icon-wrap { color: #10b981; animation: popIn 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275); }
        @keyframes popIn {
          from { transform: scale(0.5); opacity: 0; }
          to   { transform: scale(1);   opacity: 1; }
        }
        .success-state h3 { font-size: 22px; font-weight: 700; color: #e4e7f0; }
        .success-state p  { color: #9ca3af; font-size: 15px; max-width: 360px; line-height: 1.6; }

        /* ── Sidebar ─────────────────────────────── */
        .support-sidebar { display: flex; flex-direction: column; gap: 16px; }
        .info-card {
          background: rgba(26,31,53,0.6);
          border: 1px solid rgba(255,255,255,0.05);
          border-radius: 16px;
          padding: 20px;
          animation: fadeIn 0.5s ease-out 0.2s both;
        }
        .info-card.highlight {
          background: linear-gradient(135deg, rgba(59,130,246,0.08) 0%, rgba(147,51,234,0.08) 100%);
          border-color: rgba(96,165,250,0.2);
        }
        .info-card h3 { font-size: 15px; font-weight: 700; color: #e4e7f0; margin-bottom: 10px; }
        .info-card p  { font-size: 14px; color: #9ca3af; line-height: 1.6; }
        .info-card strong { color: #60a5fa; }
        .info-list { list-style: none; padding: 0; display: flex; flex-direction: column; gap: 8px; }
        .info-list li {
          font-size: 14px; color: #9ca3af; padding-left: 18px; position: relative; line-height: 1.5;
        }
        .info-list li::before {
          content: '→';
          position: absolute; left: 0;
          color: #60a5fa;
        }
        .tg-btn {
          display: inline-flex;
          align-items: center;
          margin-top: 14px;
          padding: 10px 20px;
          background: rgba(37,150,190,0.15);
          border: 1.5px solid rgba(37,150,190,0.4);
          border-radius: 10px;
          color: #67d8f5;
          font-size: 14px;
          font-weight: 600;
          text-decoration: none;
          transition: all 0.2s;
        }
        .tg-btn:hover { background: rgba(37,150,190,0.25); transform: translateY(-1px); }

        /* ── Spinner ─────────────────────────────── */
        .spin { animation: spinAnim 1s linear infinite; }
        @keyframes spinAnim {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }

        /* ── Responsive ──────────────────────────── */
        @media (max-width: 900px) {
          .support-layout { grid-template-columns: 1fr; }
          .support-sidebar { order: -1; display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
          .info-card.highlight { grid-column: 1 / -1; }
        }
        @media (max-width: 640px) {
          .dashboard-main { padding: 20px; }
          .dashboard-header { padding: 16px 20px; flex-direction: column; gap: 16px; }
          .header-left { width: 100%; flex-direction: column; gap: 16px; }
          .home-hero-section { flex-direction: column; gap: 20px; text-align: center; }
          .home-hero-actions { width: 100%; }
          .form-row { grid-template-columns: 1fr; }
          .category-grid { grid-template-columns: 1fr; }
          .support-sidebar { display: flex; flex-direction: column; }
          .support-card { padding: 20px; }
        }
      `}</style>
    </div>
  );
};

export default SupportPage;