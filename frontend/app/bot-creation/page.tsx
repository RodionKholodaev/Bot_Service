"use client"
import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Bot, Key, TrendingUp, TrendingDown, Settings, AlertCircle, Info, ChevronRight, ArrowLeft, Check, Target, Shield } from 'lucide-react';
import { apiFetch, ApiError } from '@/lib/api';
import type { BotCreatePayload, FilterRule, Indicator, Timeframe } from '@/lib/types';
import './create-bot.css';

const CreateBotPage = () => {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);
  const [formData, setFormData] = useState({
    // Шаг 1: API ключ (на MVP не отправляются на бэкенд — поля просто визуально)
    apiKey: '',
    apiSecret: '',
    exchange: 'binance',

    // Шаг 2: Торговая пара и плечо
    tradingPair: '',
    leverage: '1',
    algorithm: 'long', // long | short

    // Шаг 3: Индикаторы
    strategyPreset: 'custom', // conservative | moderate | aggressive | custom
    filters: [] as FilterRule[],

    // Шаг 4: Имя + выход из сделки
    botName: '',
    takeProfit: '2',
    stopLoss: '',
    useStopLoss: false,
    trailingStop: false, // на бэк не отправляется
  });

  const [showIndicatorTooltip, setShowIndicatorTooltip] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const strategyPresets: Record<string, {
    name: string;
    description: string;
    icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }>;
    color: string;
    filters: FilterRule[];
    takeProfit: string;
    stopLoss: string;
    useStopLoss: boolean;
  }> = {
    conservative: {
      name: 'Консервативный',
      description: 'Минимальный риск, небольшая прибыль',
      icon: Shield,
      color: '#10b981',
      filters: [
        { indicator: 'rsi', timeframe: '15m', condition: 'less', value: 25 },
        { indicator: 'cci', timeframe: '15m', condition: 'less', value: -120 },
      ],
      takeProfit: '1.5',
      stopLoss: '1',
      useStopLoss: true,
    },
    moderate: {
      name: 'Умеренный',
      description: 'Баланс риска и прибыли',
      icon: TrendingUp,
      color: '#60a5fa',
      filters: [
        { indicator: 'rsi', timeframe: '15m', condition: 'less', value: 30 },
        { indicator: 'cci', timeframe: '15m', condition: 'less', value: -100 },
      ],
      takeProfit: '2.5',
      stopLoss: '1.5',
      useStopLoss: true,
    },
    aggressive: {
      name: 'Агрессивный',
      description: 'Высокий риск, максимальная прибыль',
      icon: Target,
      color: '#f59e0b',
      filters: [
        { indicator: 'rsi', timeframe: '5m', condition: 'less', value: 35 },
        { indicator: 'cci', timeframe: '5m', condition: 'less', value: -50 },
      ],
      takeProfit: '5',
      stopLoss: '2',
      useStopLoss: true,
    },
  };

  const indicatorInfo = {
    rsi: {
      name: 'RSI (Индекс относительной силы)',
      description:
        'Показывает перекупленность или перепроданность актива. Значения ниже 30 — сигнал к покупке, выше 70 — к продаже.',
    },
    cci: {
      name: 'CCI (Индекс товарного канала)',
      description:
        'Значения ниже -100 — перепроданность (сигнал на лонг), выше +100 — перекупленность (сигнал на шорт).',
    },
  };

  const popularPairs = [
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT',
    'XRP/USDT', 'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT',
  ];

  const handlePresetSelect = (preset: string) => {
    const presetData = strategyPresets[preset];
    setFormData({
      ...formData,
      strategyPreset: preset,
      filters: presetData.filters,
      takeProfit: presetData.takeProfit,
      stopLoss: presetData.stopLoss,
      useStopLoss: presetData.useStopLoss,
    });
  };

  const handleNext = () => {
    if (currentStep < 4) setCurrentStep(currentStep + 1);
  };

  const handleBack = () => {
    if (currentStep > 1) setCurrentStep(currentStep - 1);
  };

  // ── Сабмит ─────────────────────────────────────────────

  // "BTC/USDT" → "BTC/USDT:USDT". Если уже с двоеточием — оставляем как есть.
  const toFuturesPair = (raw: string): string => {
    const trimmed = raw.trim().toUpperCase();
    if (trimmed.includes(':')) return trimmed;
    return `${trimmed}:USDT`;
  };

  // Собираем фильтры из включённых индикаторов в custom-режиме.
  // Логика та же, что в backend/strategy_presets.py:
  //   long  → "less" с oversold-уровнем
  //   short → "greater" с overbought-уровнем


  const validateBeforeSubmit = (): string | null => {
    if (!formData.botName.trim()) return 'Укажите имя бота';
    if (!formData.tradingPair.trim()) return 'Выберите торговую пару';
    if (!formData.takeProfit || Number(formData.takeProfit) <= 0)
      return 'Укажите Take Profit больше 0';
    if (formData.useStopLoss && (!formData.stopLoss || Number(formData.stopLoss) <= 0))
      return 'Укажите Stop Loss больше 0';
    if (formData.strategyPreset === 'custom') {
      if (formData.filters.length === 0) return 'Добавьте хотя бы один индикатор';
    }
    return null;
  };

  const handleSubmit = async () => {
    const validationError = validateBeforeSubmit();
    if (validationError) {
      setSubmitError(validationError);
      return;
    }
    setSubmitError(null);

    const direction = formData.algorithm as 'long' | 'short';

    const payload: BotCreatePayload = {
      name: formData.botName.trim(),
      pair: toFuturesPair(formData.tradingPair),
      leverage: Number(formData.leverage),
      direction,
      strategy_preset: formData.strategyPreset as BotCreatePayload['strategy_preset'],
      take_profit_percent: Number(formData.takeProfit),
      stop_loss_enabled: formData.useStopLoss,
      stop_loss_percent: formData.useStopLoss ? Number(formData.stopLoss) : null,
      dry_run: true,
    };

    // Для custom режима подкладываем фильтры. Для пресетов — не нужно,
    // бэкенд раскроет сам по словарю presets.
    if (formData.strategyPreset === 'custom') {
      if (direction === 'long') {
        payload.entry_filters_long = formData.filters;
      } else {
        payload.entry_filters_short = formData.filters;
      }
    }

    setSubmitting(true);
    try {
      await apiFetch('/bots', { method: 'POST', body: payload });
      router.push('/home');
    } catch (err) {
      if (err instanceof ApiError) {
        setSubmitError(err.message);
      } else {
        setSubmitError('Не удалось создать бота');
      }
      setSubmitting(false);
    }
  };

  // ── Рендеры шагов ──────────────────────────────────────

  const renderStepIndicator = () => (
    <div className="step-indicator">
      {[1, 2, 3, 4].map((step) => (
        <div
          key={step}
          className={`step-item ${currentStep >= step ? 'active' : ''} ${
            currentStep === step ? 'current' : ''
          }`}
        >
          <div className="step-circle">
            {currentStep > step ? <Check size={16} /> : step}
          </div>
          <div className="step-label">
            {step === 1 && 'API ключ'}
            {step === 2 && 'Пара и плечо'}
            {step === 3 && 'Стратегия'}
            {step === 4 && 'Имя и TP/SL'}
          </div>
        </div>
      ))}
    </div>
  );

  const renderStep1 = () => (
    <div className="step-content">
      <div className="step-header">
        <Key size={32} className="step-icon" />
        <h2>Подключение к бирже</h2>
        <p>Введите API ключи для доступа к вашему аккаунту на бирже (необязательно на этапе тестирования)</p>
      </div>

      <div className="form-group">
        <label>Биржа</label>
        <select
          value={formData.exchange}
          onChange={(e) => setFormData({ ...formData, exchange: e.target.value })}
          className="form-select"
        >
          <option value="binance">Binance</option>
          <option value="bybit">Bybit</option>
          <option value="okx">OKX</option>
        </select>
      </div>

      <div className="form-group">
        <label>
          API Key
          <span
            className="tooltip-trigger"
            onMouseEnter={() => setShowIndicatorTooltip('apiKey')}
            onMouseLeave={() => setShowIndicatorTooltip(null)}
          >
            <Info size={14} />
          </span>
        </label>
        <input
          type="text"
          value={formData.apiKey}
          onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
          placeholder="Введите API ключ"
          className="form-input"
        />
        {showIndicatorTooltip === 'apiKey' && (
          <div className="tooltip">
            Создайте API ключ в настройках биржи с правами на торговлю
          </div>
        )}
      </div>

      <div className="form-group">
        <label>
          API Secret
          <span
            className="tooltip-trigger"
            onMouseEnter={() => setShowIndicatorTooltip('apiSecret')}
            onMouseLeave={() => setShowIndicatorTooltip(null)}
          >
            <Info size={14} />
          </span>
        </label>
        <input
          type="password"
          value={formData.apiSecret}
          onChange={(e) => setFormData({ ...formData, apiSecret: e.target.value })}
          placeholder="Введите API Secret"
          className="form-input"
        />
        {showIndicatorTooltip === 'apiSecret' && (
          <div className="tooltip">
            Секретный ключ отображается только один раз при создании
          </div>
        )}
      </div>

      <div className="info-banner">
        <AlertCircle size={18} />
        <div>
          <strong>На этапе тестирования</strong> бот работает в режиме dry-run и API ключи не используются.
          Поля можно оставить пустыми.
        </div>
      </div>
    </div>
  );

  const renderStep2 = () => (
    <div className="step-content">
      <div className="step-header">
        <TrendingUp size={32} className="step-icon" />
        <h2>Торговая пара и плечо</h2>
        <p>Выберите актив для торговли и настройте параметры</p>
      </div>

      <div className="form-group">
        <label>Торговая пара</label>
        <input
          type="text"
          value={formData.tradingPair}
          onChange={(e) =>
            setFormData({ ...formData, tradingPair: e.target.value.toUpperCase() })
          }
          placeholder="Например: BTC/USDT"
          className="form-input"
        />
        <div className="popular-pairs">
          {popularPairs.map((pair) => (
            <button
              key={pair}
              onClick={() => setFormData({ ...formData, tradingPair: pair })}
              className={`pair-btn ${formData.tradingPair === pair ? 'active' : ''}`}
            >
              {pair}
            </button>
          ))}
        </div>
      </div>

      <div className="form-group">
        <label>
          Плечо (кредитное плечо)
          <span
            className="tooltip-trigger"
            onMouseEnter={() => setShowIndicatorTooltip('leverage')}
            onMouseLeave={() => setShowIndicatorTooltip(null)}
          >
            <Info size={14} />
          </span>
        </label>
        <div className="leverage-selector">
          <input
            type="range"
            min="1"
            max="20"
            value={formData.leverage}
            onChange={(e) => setFormData({ ...formData, leverage: e.target.value })}
            className="leverage-slider"
          />
          <div className="leverage-value">x{formData.leverage}</div>
        </div>
        {showIndicatorTooltip === 'leverage' && (
          <div className="tooltip">
            Плечо увеличивает потенциальную прибыль и риск. Новичкам рекомендуется x1-x3
          </div>
        )}
        {parseInt(formData.leverage) > 5 && (
          <div className="warning-banner">
            <AlertCircle size={16} />
            <span>Высокое плечо увеличивает риск ликвидации. Будьте осторожны!</span>
          </div>
        )}
      </div>

      <div className="form-group">
        <label>Направление торговли</label>
        <div className="algorithm-selector">
          <button
            className={`algorithm-btn ${formData.algorithm === 'long' ? 'active long' : ''}`}
            onClick={() => setFormData({ ...formData, algorithm: 'long' })}
          >
            <TrendingUp size={20} />
            <div>
              <strong>Лонг</strong>
              <span>Рост цены</span>
            </div>
          </button>
          <button
            className={`algorithm-btn ${formData.algorithm === 'short' ? 'active short' : ''}`}
            onClick={() => setFormData({ ...formData, algorithm: 'short' })}
          >
            <TrendingDown size={20} />
            <div>
              <strong>Шорт</strong>
              <span>Падение цены</span>
            </div>
          </button>
        </div>
      </div>
    </div>
  );

  const renderStep3 = () => (
    <div className="step-content">
      <div className="step-header">
        <Settings size={32} className="step-icon" />
        <h2>Стратегия входа</h2>
        <p>Выберите готовую стратегию или настройте индикаторы вручную</p>
      </div>

      <div className="preset-selector">
        {Object.entries(strategyPresets).map(([key, preset]) => {
          const Icon = preset.icon;
          return (
            <button
              key={key}
              className={`preset-card ${formData.strategyPreset === key ? 'active' : ''}`}
              onClick={() => handlePresetSelect(key)}
              style={formData.strategyPreset === key ? { borderColor: preset.color } : {}}
            >
              <Icon size={24} style={{ color: preset.color }} />
              <strong>{preset.name}</strong>
              <span>{preset.description}</span>
              {formData.strategyPreset === key && (
                <div className="preset-check">
                  <Check size={16} />
                </div>
              )}
            </button>
          );
        })}
        <button
          className={`preset-card ${formData.strategyPreset === 'custom' ? 'active' : ''}`}
          onClick={() => setFormData({ ...formData, strategyPreset: 'custom' })}
        >
          <Settings size={24} style={{ color: '#8b5cf6' }} />
          <strong>Свои настройки</strong>
          <span>Настроить вручную</span>
          {formData.strategyPreset === 'custom' && (
            <div className="preset-check">
              <Check size={16} />
            </div>
          )}
        </button>
      </div>

      {formData.strategyPreset === 'custom' && (
        <div className="indicators-config">
          <h3>Индикаторы входа</h3>

          {formData.filters.map((filter, idx) => (
            <div key={idx} className="filter-row">
              <select
                value={filter.indicator}
                onChange={(e) => {
                  const updated = [...formData.filters];
                  updated[idx] = { ...updated[idx], indicator: e.target.value as Indicator };
                  setFormData({ ...formData, filters: updated });
                }}
                className="form-select filter-select"
              >
                <option value="rsi">RSI</option>
                <option value="cci">CCI</option>
              </select>

              <select
                value={filter.timeframe}
                onChange={(e) => {
                  const updated = [...formData.filters];
                  updated[idx] = { ...updated[idx], timeframe: e.target.value as Timeframe };
                  setFormData({ ...formData, filters: updated });
                }}
                className="form-select filter-select"
              >
                <option value="1m">1m</option>
                <option value="5m">5m</option>
                <option value="15m">15m</option>
                <option value="30m">30m</option>
                <option value="1h">1h</option>
                <option value="4h">4h</option>
              </select>

              <select
                value={filter.condition}
                onChange={(e) => {
                  const updated = [...formData.filters];
                  updated[idx] = { ...updated[idx], condition: e.target.value as FilterRule['condition'] };
                  setFormData({ ...formData, filters: updated });
                }}
                className="form-select filter-select"
              >
                <option value="less">{'<'} меньше</option>
                <option value="greater">{'>'} больше</option>
              </select>

              <input
                type="number"
                value={filter.value}
                onChange={(e) => {
                  const updated = [...formData.filters];
                  updated[idx] = { ...updated[idx], value: Number(e.target.value) };
                  setFormData({ ...formData, filters: updated });
                }}
                className="form-input filter-input"
                placeholder="30"
              />

              <button
                className="filter-remove-btn"
                onClick={() =>
                  setFormData({
                    ...formData,
                    filters: formData.filters.filter((_, i) => i !== idx),
                  })
                }
              >
                ✕
              </button>
            </div>
          ))}

          <button
            className="filter-add-btn"
            onClick={() =>
              setFormData({
                ...formData,
                filters: [
                  ...formData.filters,
                  { indicator: 'rsi' as Indicator, timeframe: '5m' as Timeframe, condition: 'less', value: 30 },
                ],
              })
            }
          >
            <span>＋</span> Добавить индикатор
          </button>
        </div>
      )}
    </div>
  );

  const renderStep4 = () => (
    <div className="step-content">
      <div className="step-header">
        <Target size={32} className="step-icon" />
        <h2>Имя и выход из сделки</h2>
        <p>Дайте боту имя и настройте условия фиксации прибыли и ограничения убытков</p>
      </div>

      <div className="form-group">
        <label>Имя бота</label>
        <input
          type="text"
          value={formData.botName}
          onChange={(e) => setFormData({ ...formData, botName: e.target.value })}
          placeholder="Например: BTC скальпер"
          maxLength={100}
          className="form-input"
        />
      </div>

      <div className="form-group">
        <label>
          Take Profit (%)
          <span
            className="tooltip-trigger"
            onMouseEnter={() => setShowIndicatorTooltip('tp')}
            onMouseLeave={() => setShowIndicatorTooltip(null)}
          >
            <Info size={14} />
          </span>
        </label>
        <input
          type="number"
          step="0.1"
          value={formData.takeProfit}
          onChange={(e) => setFormData({ ...formData, takeProfit: e.target.value })}
          placeholder="2.0"
          className="form-input"
        />
        {showIndicatorTooltip === 'tp' && (
          <div className="tooltip">
            Процент прибыли, при котором бот автоматически закроет сделку
          </div>
        )}
      </div>

      <div className="form-group">
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={formData.useStopLoss}
            onChange={(e) => setFormData({ ...formData, useStopLoss: e.target.checked })}
          />
          <span>Использовать Stop Loss</span>
          <span
            className="tooltip-trigger"
            onMouseEnter={() => setShowIndicatorTooltip('sl')}
            onMouseLeave={() => setShowIndicatorTooltip(null)}
          >
            <Info size={14} />
          </span>
        </label>
        {showIndicatorTooltip === 'sl' && (
          <div className="tooltip">
            Автоматическое закрытие сделки при достижении определённого убытка
          </div>
        )}
      </div>

      {formData.useStopLoss && (
        <>
          <div className="form-group">
            <label>Stop Loss (%)</label>
            <input
              type="number"
              step="0.1"
              value={formData.stopLoss}
              onChange={(e) => setFormData({ ...formData, stopLoss: e.target.value })}
              placeholder="1.5"
              className="form-input"
            />
          </div>

          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={formData.trailingStop}
                onChange={(e) => setFormData({ ...formData, trailingStop: e.target.checked })}
              />
              <span>Трейлинг стоп</span>
              <span
                className="tooltip-trigger"
                onMouseEnter={() => setShowIndicatorTooltip('trailing')}
                onMouseLeave={() => setShowIndicatorTooltip(null)}
              >
                <Info size={14} />
              </span>
            </label>
            {showIndicatorTooltip === 'trailing' && (
              <div className="tooltip">
                Стоп-лосс будет следовать за ценой, сохраняя заданное расстояние
              </div>
            )}
          </div>
        </>
      )}

      <div className="summary-card">
        <h3>Итоговые настройки</h3>
        <div className="summary-row">
          <span>Имя бота:</span>
          <strong>{formData.botName || 'Не указано'}</strong>
        </div>
        <div className="summary-row">
          <span>Биржа:</span>
          <strong>{formData.exchange.toUpperCase()}</strong>
        </div>
        <div className="summary-row">
          <span>Пара:</span>
          <strong>{formData.tradingPair || 'Не выбрана'}</strong>
        </div>
        <div className="summary-row">
          <span>Плечо:</span>
          <strong>x{formData.leverage}</strong>
        </div>
        <div className="summary-row">
          <span>Направление:</span>
          <strong>{formData.algorithm === 'long' ? '📈 Лонг' : '📉 Шорт'}</strong>
        </div>
        <div className="summary-row">
          <span>Стратегия:</span>
          <strong>
            {formData.strategyPreset === 'custom'
              ? 'Своя'
              : strategyPresets[formData.strategyPreset]?.name}
          </strong>
        </div>
        <div className="summary-row">
          <span>Take Profit:</span>
          <strong className="profit-text">{formData.takeProfit}%</strong>
        </div>
        {formData.useStopLoss && (
          <div className="summary-row">
            <span>Stop Loss:</span>
            <strong className="loss-text">{formData.stopLoss}%</strong>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="create-bot-page">
      <div className="page-header">
        <button className="back-btn" onClick={() => window.history.back()}>
          <ArrowLeft size={20} />
          Назад
        </button>
        <div className="page-title">
          <Bot size={28} />
          <h1>Создание торгового бота</h1>
        </div>
      </div>

      <div className="create-bot-container">
        {renderStepIndicator()}

        <div className="form-container">
          {currentStep === 1 && renderStep1()}
          {currentStep === 2 && renderStep2()}
          {currentStep === 3 && renderStep3()}
          {currentStep === 4 && renderStep4()}

          {submitError && currentStep === 4 && (
            <div className="warning-banner" style={{ marginTop: 16 }}>
              <AlertCircle size={16} />
              <span>{submitError}</span>
            </div>
          )}

          <div className="form-actions">
            {currentStep > 1 && (
              <button
                className="btn-secondary"
                onClick={handleBack}
                disabled={submitting}
              >
                Назад
              </button>
            )}
            {currentStep < 4 ? (
              <button className="btn-primary" onClick={handleNext}>
                Далее
                <ChevronRight size={20} />
              </button>
            ) : (
              <button
                className="btn-primary"
                onClick={handleSubmit}
                disabled={submitting}
              >
                <Bot size={20} />
                {submitting ? 'Создаём бота...' : 'Создать бота'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CreateBotPage;