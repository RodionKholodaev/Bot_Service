"use client"
import React, { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { Bot, TrendingUp, Shield, Zap, BarChart2, Settings, ChevronRight, ArrowRight, Activity, Lock, Globe } from 'lucide-react';
import './landing.css';

const LandingPage = () => {
  const [scrolled, setScrolled] = useState(false);
  const heroRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const features = [
    {
      icon: Zap,
      title: 'Быстрый старт',
      desc: 'Запустите первого бота за 5 минут — без знания программирования и технического анализа.',
      color: '#f59e0b',
    },
    {
      icon: BarChart2,
      title: 'RSI & CCI стратегии',
      desc: 'Готовые шаблоны сигналов на базе популярных индикаторов. Или настройте условия сами.',
      color: '#60a5fa',
    },
    {
      icon: Shield,
      title: 'Take Profit / Stop Loss',
      desc: 'Гибкие условия выхода: фиксированный SL, трейлинг-стоп или торговля без стопа.',
      color: '#10b981',
    },
    {
      icon: Settings,
      title: 'Управление ботами',
      desc: 'Запуск, остановка, мониторинг состояния и история сделок — всё в одном месте.',
      color: '#a78bfa',
    },
    {
      icon: Lock,
      title: 'Безопасность ключей',
      desc: 'API-ключи хранятся в зашифрованном виде и используются только для торговли.',
      color: '#f472b6',
    },
    {
      icon: Globe,
      title: 'Binance & Bybit',
      desc: 'Поддержка ведущих криптобирж. Торговля на фьючерсах с настраиваемым плечом.',
      color: '#34d399',
    },
  ];

  const steps = [
    { num: '01', title: 'Подключите биржу', desc: 'Вставьте API-ключ от Binance или Bybit — это займёт минуту.' },
    { num: '02', title: 'Настройте стратегию', desc: 'Выберите пресет или настройте индикаторы (RSI, CCI) вручную.' },
    { num: '03', title: 'Запустите бота', desc: 'Бот стартует в изолированном контейнере и начинает торговать.' },
    { num: '04', title: 'Следите за P&L', desc: 'Смотрите сделки, статистику и управляйте ботами в реальном времени.' },
  ];

  return (
    <div className="landing-page">
      {/* Navbar */}
      <nav className={`landing-nav ${scrolled ? 'scrolled' : ''}`}>
        <div className="nav-inner">
          <div className="nav-logo">
            <Bot size={24} />
            <span>CryptoBot</span>
          </div>
          <div className="nav-links">
            <a href="#features">Возможности</a>
            <a href="#how">Как это работает</a>
          </div>
          <div className="nav-actions">
            <Link href="/auth?mode=login" className="nav-btn-ghost">Войти</Link>
            <Link href="/auth?mode=register" className="nav-btn-primary">Начать бесплатно</Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="hero-section" ref={heroRef}>
        <div className="hero-bg">
          <div className="hero-glow glow-1" />
          <div className="hero-glow glow-2" />
          <div className="hero-grid" />
        </div>
        <div className="hero-content">
          <div className="hero-badge">
            <Activity size={14} />
            <span>Автоматическая торговля на фьючерсах</span>
          </div>
          <h1 className="hero-title">
            Торговые боты<br />
            <span className="hero-accent">без кода</span><br />
            и сложностей
          </h1>
          <p className="hero-subtitle">
            Подключите биржу, выберите стратегию и запустите бота за 5 минут.
            Ничего лишнего — только результат.
          </p>
          <div className="hero-actions">
            <Link href="/auth?mode=register" className="hero-btn-primary">
              Создать первого бота
              <ArrowRight size={18} />
            </Link>
            <Link href="/auth?mode=login" className="hero-btn-ghost">
              Уже есть аккаунт
            </Link>
          </div>
          <div className="hero-stats">
            <div className="stat-item">
              <strong>Binance</strong>
              <span>& Bybit</span>
            </div>
            <div className="stat-divider" />
            <div className="stat-item">
              <strong>RSI / CCI</strong>
              <span>Индикаторы</span>
            </div>
            <div className="stat-divider" />
            <div className="stat-item">
              <strong>Freqtrade</strong>
              <span>Движок</span>
            </div>
          </div>
        </div>

        {/* Floating card preview */}
        <div className="hero-card-preview">
          <div className="preview-card">
            <div className="preview-header">
              <div className="preview-dot green" />
              <span>BTC/USDT • x10 • Long</span>
              <span className="preview-pnl">+4.2%</span>
            </div>
            <div className="preview-chart">
              <svg viewBox="0 0 200 60" fill="none">
                <polyline
                  points="0,50 20,44 40,46 60,35 80,30 100,32 120,22 140,18 160,14 180,10 200,8"
                  stroke="#10b981" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"
                />
                <polyline
                  points="0,50 20,44 40,46 60,35 80,30 100,32 120,22 140,18 160,14 180,10 200,8"
                  stroke="url(#chartGrad)" strokeWidth="0" fill="url(#chartGrad)"
                />
                <defs>
                  <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10b981" stopOpacity="0.3" />
                    <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
                  </linearGradient>
                </defs>
              </svg>
            </div>
            <div className="preview-indicators">
              <div className="pi-badge blue">RSI 28</div>
              <div className="pi-badge amber">CCI -95</div>
              <div className="pi-badge green">Сигнал: Вход</div>
            </div>
          </div>

          <div className="preview-card small">
            <div className="preview-mini-row">
              <Bot size={14} />
              <span>ETH/USDT</span>
              <span className="loss-text">-1.1%</span>
            </div>
            <div className="preview-mini-row">
              <Bot size={14} />
              <span>SOL/USDT</span>
              <span className="profit-text">+7.8%</span>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="features-section" id="features">
        <div className="section-inner">
          <div className="section-label">Возможности</div>
          <h2 className="section-title">Всё что нужно для<br />автоматической торговли</h2>
          <div className="features-grid">
            {features.map((f) => {
              const Icon = f.icon;
              return (
                <div className="feature-card" key={f.title} style={{ '--accent': f.color } as React.CSSProperties}>
                  <div className="feature-icon">
                    <Icon size={22} />
                  </div>
                  <h3>{f.title}</h3>
                  <p>{f.desc}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="how-section" id="how">
        <div className="section-inner">
          <div className="section-label">Как это работает</div>
          <h2 className="section-title">Запустите бота<br />за 4 шага</h2>
          <div className="steps-list">
            {steps.map((s, i) => (
              <div className="step-card" key={s.num}>
                <div className="step-num">{s.num}</div>
                <div className="step-body">
                  <h3>{s.title}</h3>
                  <p>{s.desc}</p>
                </div>
                {i < steps.length - 1 && <ChevronRight size={20} className="step-arrow" />}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="cta-section">
        <div className="cta-glow" />
        <div className="cta-inner">
          <h2>Готовы начать?</h2>
          <p>Создайте аккаунт и запустите первого бота прямо сейчас.</p>
          <Link href="/auth?mode=register" className="hero-btn-primary">
            Зарегистрироваться
            <ArrowRight size={18} />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="footer-inner">
          <div className="footer-logo">
            <Bot size={20} />
            <span>CryptoBot</span>
          </div>
          <p className="footer-note">Торговля несёт риски. Используйте ответственно.</p>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;