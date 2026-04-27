"use client"
import React, { useState } from 'react';
import { TrendingUp, Bot, Wallet, DollarSign, Plus, Settings, BookOpen, MessageCircle, BarChart3, Pause, AlertCircle, Zap, ChevronRight, CreditCard } from 'lucide-react';
import Link from 'next/link';

const TradingBotDashboard = () => {
  const [serviceBalance, setServiceBalance] = useState(850); // ₽
  const [showTopUpModal, setShowTopUpModal] = useState(false);
  
  // Mock data
  const stats = {
    activeBots: 3,
    weeklyProfit: 247.50,
    fundsUnderManagement: 5420.00,
    exchangeBalance: 6150.30
  };

  const bots = [
    { id: 1, name: 'BTC Scalper Pro', status: 'active', profit: 125.40, exchange: 'Binance', pair: 'BTC/USDT' },
    { id: 2, name: 'ETH Grid Trader', status: 'active', profit: 89.30, exchange: 'Bybit', pair: 'ETH/USDT' },
    { id: 3, name: 'DOGE Momentum', status: 'active', profit: 32.80, exchange: 'Binance', pair: 'DOGE/USDT' },
  ];

  const getBalanceStatus = (balance) => {
    if (balance < 100) return { color: 'red', daysLeft: 1, status: 'critical' };
    if (balance < 1000) return { color: 'orange', daysLeft: 5, status: 'low' };
    return { color: 'green', daysLeft: 14, status: 'good' };
  };

  const balanceStatus = getBalanceStatus(serviceBalance);

  return (
    <div className="dashboard-container">
      {/* Critical Balance Alert */}
      {balanceStatus.status === 'critical' && (
        <div className="balance-alert critical">
          <AlertCircle size={20} />
          <span>⚠️ Критический баланс! Боты остановятся через {balanceStatus.daysLeft} день. Пополните баланс сейчас.</span>
          <button className="btn-alert-action" onClick={() => setShowTopUpModal(true)}>
            Пополнить сейчас
          </button>
        </div>
      )}

      {balanceStatus.status === 'low' && (
        <div className="balance-alert warning">
          <AlertCircle size={18} />
          <span>Баланс заканчивается. Хватит примерно на {balanceStatus.daysLeft} дней работы.</span>
          <button className="btn-alert-action-small" onClick={() => setShowTopUpModal(true)}>
            Пополнить
          </button>
        </div>
      )}

      {/* Header */}
      <header className="dashboard-header">
        <div className="header-left">
          <div className="logo">
            <Zap size={28} />
            <span>CryptoBot</span>
          </div>
          <nav className="main-nav">
            <a href="#" className="nav-item active">Главная</a>
            <a href="#" className="nav-item">Статистика</a>
            <a href="#" className="nav-item">Обучение</a>
          </nav>
        </div>
        <div className="header-right">
          <div className={`balance-indicator ${balanceStatus.status}`} onClick={() => setShowTopUpModal(true)}>
            <CreditCard size={16} />
            <span className="balance-amount">{serviceBalance.toLocaleString('ru-RU')} ₽</span>
          </div>
          <button className="btn-icon" onClick={() => setShowTopUpModal(true)}>
            <Plus size={20} />
          </button>
          <Link href="/settings">
            <button className="btn-icon">
              <Settings size={20} />
            </button>
          </Link>
        </div>
      </header>

      {/* Main Content */}
      <main className="dashboard-main">
        {/* Hero Section */}
        <section className="home-hero-section">
          <div className="home-hero-content">
            <h1>Добро пожаловать в панель управления</h1>
            <p>Ваши торговые боты работают круглосуточно</p>
          </div>
          <div className="home-hero-actions">
            <Link href="/bot-creation">
              <button className="btn-primary">
                <Plus size={20} />
                Создать бота
              </button>
            </Link>
            <button className="btn-secondary">
              <BookOpen size={20} />
              Как это работает?
            </button>
          </div>
        </section>

        {/* Stats Grid */}
        <section className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon active">
              <Bot size={24} />
            </div>
            <div className="stat-content">
              <div className="stat-label">Активные боты</div>
              <div className="stat-value">{stats.activeBots}</div>
            </div>
          </div>

          <div className="stat-card profit">
            <div className="stat-icon profit">
              <TrendingUp size={24} />
            </div>
            <div className="stat-content">
              <div className="stat-label">Прибыль за неделю</div>
              <div className="stat-value profit">+${stats.weeklyProfit}</div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon">
              <DollarSign size={24} />
            </div>
            <div className="stat-content">
              <div className="stat-label">В управлении</div>
              <div className="stat-value">${stats.fundsUnderManagement.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon">
              <Wallet size={24} />
            </div>
            <div className="stat-content">
              <div className="stat-label">Баланс на бирже</div>
              <div className="stat-value">${stats.exchangeBalance.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
            </div>
          </div>
        </section>

        {/* Active Bots */}
        <section className="bots-section">
          <div className="section-header">
            <h2>Активные боты</h2>
            <button className="btn-text">
              Смотреть все <ChevronRight size={16} />
            </button>
          </div>

          {bots.length > 0 ? (
            <div className="bots-list">
              {bots.map(bot => (
                <div key={bot.id} className="bot-card">
                  <div className="bot-header">
                    <div className="bot-info">
                      <div className="bot-status-indicator active"></div>
                      <div>
                        <h3>{bot.name}</h3>
                        <p className="bot-meta">{bot.exchange} • {bot.pair}</p>
                      </div>
                    </div>
                    <div className="bot-actions">
                      <button className="btn-icon-small">
                        <Pause size={16} />
                      </button>
                      <button className="btn-icon-small">
                        <Settings size={16} />
                      </button>
                    </div>
                  </div>
                  <div className="bot-stats">
                    <div className="bot-stat">
                      <span className="bot-stat-label">Прибыль</span>
                      <span className="bot-stat-value profit">+${bot.profit}</span>
                    </div>
                    <button className="btn-bot-details">
                      <BarChart3 size={16} />
                      Статистика
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <Bot size={64} />
              <h3>У вас пока нет активных ботов</h3>
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
          <button className="action-card">
            <MessageCircle size={24} />
            <div>
              <h3>Поддержка</h3>
              <p>Задать вопрос</p>
            </div>
            <ChevronRight size={20} />
          </button>
          <button className="action-card">
            <BarChart3 size={24} />
            <div>
              <h3>Детальная статистика</h3>
              <p>Анализ и графики</p>
            </div>
            <ChevronRight size={20} />
          </button>
          <button className="action-card">
            <BookOpen size={24} />
            <div>
              <h3>Обучение</h3>
              <p>Гайды для новичков</p>
            </div>
            <ChevronRight size={20} />
          </button>
        </section>
      </main>

      {/* Top-up Modal */}
      {showTopUpModal && (
        <div className="modal-overlay" onClick={() => setShowTopUpModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <h2>Пополнить баланс</h2>
            <p className="modal-description">Выберите сумму пополнения или введите свою</p>
            
            <div className="topup-amounts">
              <button className="amount-btn">500 ₽</button>
              <button className="amount-btn recommended">1000 ₽</button>
              <button className="amount-btn">2000 ₽</button>
              <button className="amount-btn">5000 ₽</button>
            </div>

            <div className="custom-amount">
              <label>Или введите сумму</label>
              <input type="number" placeholder="1000" />
            </div>

            <div className="modal-actions">
              <button className="btn-secondary" onClick={() => setShowTopUpModal(false)}>
                Отмена
              </button>
              <button className="btn-primary">
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
          min-height: 100vh;
          background: linear-gradient(135deg, #0a0e1a 0%, #1a1f35 100%);
          color: #e4e7f0;
          font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
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
          background: linear-gradient(90deg, rgba(239, 68, 68, 0.15) 0%, rgba(220, 38, 38, 0.1) 100%);
          border-bottom: 2px solid rgba(239, 68, 68, 0.5);
          color: #fca5a5;
        }

        .balance-alert.warning {
          background: rgba(251, 191, 36, 0.1);
          border-bottom: 2px solid rgba(251, 191, 36, 0.3);
          color: #fcd34d;
        }

        .btn-alert-action, .btn-alert-action-small {
          margin-left: auto;
          padding: 8px 20px;
          border: none;
          border-radius: 8px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }

        .btn-alert-action {
          background: #ef4444;
          color: white;
          font-size: 14px;
        }

        .btn-alert-action-small {
          background: rgba(251, 191, 36, 0.2);
          color: #fbbf24;
          font-size: 13px;
          border: 1px solid rgba(251, 191, 36, 0.3);
        }

        .btn-alert-action:hover {
          background: #dc2626;
          transform: translateY(-1px);
        }

        .btn-alert-action-small:hover {
          background: rgba(251, 191, 36, 0.3);
        }

        /* Header */
        .dashboard-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 20px 40px;
          background: rgba(26, 31, 53, 0.6);
          backdrop-filter: blur(20px);
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
          position: sticky;
          top: 0;
          z-index: 100;
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
          cursor: pointer;
          transition: all 0.3s;
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
          animation: pulse-critical 2s ease-in-out infinite;
        }

        @keyframes pulse-critical {
          0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
          50% { box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }
        }

        .balance-indicator:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
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

        /* Main Content */
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
          background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(147, 51, 234, 0.1) 100%);
          border-radius: 20px;
          border: 1px solid rgba(96, 165, 250, 0.2);
          animation: fadeIn 0.6s ease-out;
        }

        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
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

        .home-hero-content p {
          color: #9ca3af;
          font-size: 16px;
        }

        .home-hero-actions {
          display: flex;
          gap: 12px;
        }

        .btn-primary, .btn-secondary {
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
        }

        .btn-primary {
          background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
          color: white;
          box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3);
        }

        .btn-primary:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 20px rgba(59, 130, 246, 0.4);
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

        /* Stats Grid */
        .stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 20px;
          margin-bottom: 40px;
        }

        .stat-card {
          background: rgba(26, 31, 53, 0.6);
          border: 1px solid rgba(255, 255, 255, 0.05);
          border-radius: 16px;
          padding: 24px;
          display: flex;
          gap: 16px;
          transition: all 0.3s;
          animation: slideUp 0.6s ease-out;
          animation-fill-mode: both;
        }

        .stat-card:nth-child(1) { animation-delay: 0.1s; }
        .stat-card:nth-child(2) { animation-delay: 0.2s; }
        .stat-card:nth-child(3) { animation-delay: 0.3s; }
        .stat-card:nth-child(4) { animation-delay: 0.4s; }

        @keyframes slideUp {
          from { opacity: 0; transform: translateY(30px); }
          to { opacity: 1; transform: translateY(0); }
        }

        .stat-card:hover {
          transform: translateY(-4px);
          border-color: rgba(96, 165, 250, 0.3);
          box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
        }

        .stat-card.profit {
          background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(5, 150, 105, 0.05) 100%);
          border-color: rgba(16, 185, 129, 0.2);
        }

        .stat-icon {
          width: 56px;
          height: 56px;
          border-radius: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(255, 255, 255, 0.05);
          color: #9ca3af;
        }

        .stat-icon.active {
          background: rgba(59, 130, 246, 0.15);
          color: #60a5fa;
        }

        .stat-icon.profit {
          background: rgba(16, 185, 129, 0.15);
          color: #34d399;
        }

        .stat-content {
          flex: 1;
        }

        .stat-label {
          font-size: 13px;
          color: #9ca3af;
          margin-bottom: 8px;
          font-weight: 500;
        }

        .stat-value {
          font-size: 28px;
          font-weight: 700;
          color: #e4e7f0;
        }

        .stat-value.profit {
          color: #34d399;
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
          color: #60a5fa;
          font-size: 14px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }

        .btn-text:hover {
          color: #93c5fd;
          gap: 8px;
        }

        .bots-list {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .bot-card {
          background: rgba(26, 31, 53, 0.6);
          border: 1px solid rgba(255, 255, 255, 0.05);
          border-radius: 16px;
          padding: 24px;
          transition: all 0.3s;
        }

        .bot-card:hover {
          border-color: rgba(96, 165, 250, 0.3);
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

        .bot-status-indicator {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          margin-top: 6px;
          flex-shrink: 0;
        }

        .bot-status-indicator.active {
          background: #34d399;
          box-shadow: 0 0 12px rgba(52, 211, 153, 0.6);
          animation: pulse 2s ease-in-out infinite;
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }

        .bot-info h3 {
          font-size: 18px;
          font-weight: 600;
          margin-bottom: 4px;
        }

        .bot-meta {
          font-size: 13px;
          color: #9ca3af;
        }

        .bot-actions {
          display: flex;
          gap: 8px;
        }

        .btn-icon-small {
          padding: 8px;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          color: #9ca3af;
          cursor: pointer;
          transition: all 0.2s;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .btn-icon-small:hover {
          background: rgba(255, 255, 255, 0.1);
          color: #e4e7f0;
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
          color: #9ca3af;
        }

        .bot-stat-value {
          font-size: 20px;
          font-weight: 700;
        }

        .btn-bot-details {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 8px 16px;
          background: rgba(96, 165, 250, 0.1);
          border: 1px solid rgba(96, 165, 250, 0.2);
          border-radius: 8px;
          color: #60a5fa;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }

        .btn-bot-details:hover {
          background: rgba(96, 165, 250, 0.2);
          transform: translateY(-1px);
        }

        .empty-state {
          text-align: center;
          padding: 80px 40px;
          background: rgba(26, 31, 53, 0.6);
          border: 2px dashed rgba(255, 255, 255, 0.1);
          border-radius: 16px;
          color: #9ca3af;
        }

        .empty-state svg {
          opacity: 0.3;
          margin-bottom: 24px;
        }

        .empty-state h3 {
          font-size: 20px;
          font-weight: 600;
          margin-bottom: 8px;
          color: #e4e7f0;
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
          background: rgba(26, 31, 53, 0.6);
          border: 1px solid rgba(255, 255, 255, 0.05);
          border-radius: 16px;
          cursor: pointer;
          transition: all 0.3s;
          text-align: left;
          color: inherit;
        }

        .action-card:hover {
          background: rgba(26, 31, 53, 0.8);
          border-color: rgba(96, 165, 250, 0.3);
          transform: translateY(-2px);
        }

        .action-card svg:first-child {
          color: #60a5fa;
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
          color: #9ca3af;
        }

        .action-card svg:last-child {
          color: #9ca3af;
          flex-shrink: 0;
        }

        /* Modal */
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.7);
          backdrop-filter: blur(4px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          animation: fadeIn 0.2s ease-out;
        }

        .modal-content {
          background: #1a1f35;
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 20px;
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
          color: #9ca3af;
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
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 12px;
          color: #e4e7f0;
          font-size: 18px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s;
        }

        .amount-btn:hover {
          background: rgba(255, 255, 255, 0.1);
          border-color: rgba(96, 165, 250, 0.3);
        }

        .amount-btn.recommended {
          background: rgba(59, 130, 246, 0.15);
          border-color: rgba(59, 130, 246, 0.3);
          color: #60a5fa;
          position: relative;
        }

        .amount-btn.recommended::after {
          content: 'Рекомендуем';
          position: absolute;
          top: -8px;
          right: -8px;
          background: #3b82f6;
          color: white;
          font-size: 10px;
          padding: 2px 8px;
          border-radius: 4px;
          font-weight: 700;
        }

        .custom-amount {
          margin-bottom: 24px;
        }

        .custom-amount label {
          display: block;
          font-size: 14px;
          color: #9ca3af;
          margin-bottom: 8px;
        }

        .custom-amount input {
          width: 100%;
          padding: 14px;
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 12px;
          color: #e4e7f0;
          font-size: 16px;
          font-weight: 600;
        }

        .custom-amount input:focus {
          outline: none;
          border-color: rgba(96, 165, 250, 0.5);
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

          .dashboard-main {
            padding: 20px;
          }
        }
      `}</style>
    </div>
  );
};

export default TradingBotDashboard;