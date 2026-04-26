"use client"
import React, { useState } from 'react';
import { Bot, Key, TrendingUp, TrendingDown, Settings, AlertCircle, Info, ChevronDown, ChevronRight, ArrowLeft, Check, Target, Shield } from 'lucide-react';
import './create-bot.css'; // Импортируйте отдельный CSS файл

const CreateBotPage = () => {
  const [currentStep, setCurrentStep] = useState(1);
  const [formData, setFormData] = useState({
    // Шаг 1: API ключ
    apiKey: '',
    apiSecret: '',
    exchange: 'binance',
    
    // Шаг 2: Торговая пара и плечо
    tradingPair: '',
    leverage: '1',
    algorithm: 'long', // long, short, both
    
    // Шаг 3: Индикаторы
    strategyPreset: 'custom', // conservative, moderate, aggressive, custom
    indicators: {
      rsi: { enabled: false, oversold: 30, overbought: 70 },
      macd: { enabled: false, fastPeriod: 12, slowPeriod: 26, signalPeriod: 9 },
      ema: { enabled: false, shortPeriod: 9, longPeriod: 21 },
      volume: { enabled: false, multiplier: 1.5 }
    },
    
    // Шаг 4: Выход из сделки
    takeProfit: '2',
    stopLoss: '',
    useStopLoss: false,
    trailingStop: false
  });

  const [showIndicatorTooltip, setShowIndicatorTooltip] = useState(null);

  const strategyPresets = {
    conservative: {
      name: 'Консервативный',
      description: 'Минимальный риск, небольшая прибыль',
      icon: Shield,
      color: '#10b981',
      indicators: {
        rsi: { enabled: true, oversold: 25, overbought: 75 },
        macd: { enabled: true, fastPeriod: 12, slowPeriod: 26, signalPeriod: 9 },
        ema: { enabled: true, shortPeriod: 9, longPeriod: 21 },
        volume: { enabled: false, multiplier: 1.5 }
      },
      takeProfit: '1.5',
      stopLoss: '1',
      useStopLoss: true
    },
    moderate: {
      name: 'Умеренный',
      description: 'Баланс риска и прибыли',
      icon: TrendingUp,
      color: '#60a5fa',
      indicators: {
        rsi: { enabled: true, oversold: 30, overbought: 70 },
        macd: { enabled: true, fastPeriod: 12, slowPeriod: 26, signalPeriod: 9 },
        ema: { enabled: true, shortPeriod: 9, longPeriod: 21 },
        volume: { enabled: true, multiplier: 1.5 }
      },
      takeProfit: '2.5',
      stopLoss: '1.5',
      useStopLoss: true
    },
    aggressive: {
      name: 'Агрессивный',
      description: 'Высокий риск, максимальная прибыль',
      icon: Target,
      color: '#f59e0b',
      indicators: {
        rsi: { enabled: true, oversold: 35, overbought: 65 },
        macd: { enabled: true, fastPeriod: 12, slowPeriod: 26, signalPeriod: 9 },
        ema: { enabled: false, shortPeriod: 9, longPeriod: 21 },
        volume: { enabled: true, multiplier: 2.0 }
      },
      takeProfit: '5',
      stopLoss: '2',
      useStopLoss: true
    }
  };

  const indicatorInfo = {
    rsi: {
      name: 'RSI (Индекс относительной силы)',
      description: 'Показывает перекупленность или перепроданность актива. Значения ниже 30 - сигнал к покупке, выше 70 - к продаже.'
    },
    macd: {
      name: 'MACD (Схождение/расхождение)',
      description: 'Трендовый индикатор, показывает изменение импульса. Пересечение линий - сигнал к сделке.'
    },
    ema: {
      name: 'EMA (Экспоненциальная скользящая средняя)',
      description: 'Определяет направление тренда. Пересечение быстрой и медленной EMA - сигнал к входу.'
    },
    volume: {
      name: 'Объём торгов',
      description: 'Подтверждает силу движения цены. Высокий объём усиливает сигнал других индикаторов.'
    }
  };

  const popularPairs = [
    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 
    'XRP/USDT', 'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT'
  ];

  const handlePresetSelect = (preset) => {
    const presetData = strategyPresets[preset];
    setFormData({
      ...formData,
      strategyPreset: preset,
      indicators: presetData.indicators,
      takeProfit: presetData.takeProfit,
      stopLoss: presetData.stopLoss,
      useStopLoss: presetData.useStopLoss
    });
  };

  const handleNext = () => {
    if (currentStep < 4) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleSubmit = () => {
    console.log('Создание бота с настройками:', formData);
    // Здесь будет логика создания бота
  };

  const renderStepIndicator = () => (
    <div className="step-indicator">
      {[1, 2, 3, 4].map(step => (
        <div key={step} className={`step-item ${currentStep >= step ? 'active' : ''} ${currentStep === step ? 'current' : ''}`}>
          <div className="step-circle">
            {currentStep > step ? <Check size={16} /> : step}
          </div>
          <div className="step-label">
            {step === 1 && 'API ключ'}
            {step === 2 && 'Пара и плечо'}
            {step === 3 && 'Стратегия'}
            {step === 4 && 'TP/SL'}
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
        <p>Введите API ключи для доступа к вашему аккаунту на бирже</p>
      </div>

      <div className="form-group">
        <label>Биржа</label>
        <select 
          value={formData.exchange}
          onChange={(e) => setFormData({...formData, exchange: e.target.value})}
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
          <span className="tooltip-trigger" onMouseEnter={() => setShowIndicatorTooltip('apiKey')} onMouseLeave={() => setShowIndicatorTooltip(null)}>
            <Info size={14} />
          </span>
        </label>
        <input
          type="text"
          value={formData.apiKey}
          onChange={(e) => setFormData({...formData, apiKey: e.target.value})}
          placeholder="Введите API ключ"
          className="form-input"
        />
        {showIndicatorTooltip === 'apiKey' && (
          <div className="tooltip">
            Создайте API ключ в настройках биржи с правами на спотовую торговлю
          </div>
        )}
      </div>

      <div className="form-group">
        <label>
          API Secret
          <span className="tooltip-trigger" onMouseEnter={() => setShowIndicatorTooltip('apiSecret')} onMouseLeave={() => setShowIndicatorTooltip(null)}>
            <Info size={14} />
          </span>
        </label>
        <input
          type="password"
          value={formData.apiSecret}
          onChange={(e) => setFormData({...formData, apiSecret: e.target.value})}
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
          <strong>Безопасность:</strong> Ваши ключи хранятся в зашифрованном виде и используются только для торговли
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
          onChange={(e) => setFormData({...formData, tradingPair: e.target.value.toUpperCase()})}
          placeholder="Например: BTC/USDT"
          className="form-input"
        />
        <div className="popular-pairs">
          {popularPairs.map(pair => (
            <button
              key={pair}
              onClick={() => setFormData({...formData, tradingPair: pair})}
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
          <span className="tooltip-trigger" onMouseEnter={() => setShowIndicatorTooltip('leverage')} onMouseLeave={() => setShowIndicatorTooltip(null)}>
            <Info size={14} />
          </span>
        </label>
        <div className="leverage-selector">
          <input
            type="range"
            min="1"
            max="20"
            value={formData.leverage}
            onChange={(e) => setFormData({...formData, leverage: e.target.value})}
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
            onClick={() => setFormData({...formData, algorithm: 'long'})}
          >
            <TrendingUp size={20} />
            <div>
              <strong>Лонг</strong>
              <span>Рост цены</span>
            </div>
          </button>
          <button
            className={`algorithm-btn ${formData.algorithm === 'short' ? 'active short' : ''}`}
            onClick={() => setFormData({...formData, algorithm: 'short'})}
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
          onClick={() => setFormData({...formData, strategyPreset: 'custom'})}
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
          <h3>Настройка индикаторов</h3>
          
          {/* RSI */}
          <div className="indicator-item">
            <div className="indicator-header">
              <label className="indicator-toggle">
                <input
                  type="checkbox"
                  checked={formData.indicators.rsi.enabled}
                  onChange={(e) => setFormData({
                    ...formData,
                    indicators: {
                      ...formData.indicators,
                      rsi: { ...formData.indicators.rsi, enabled: e.target.checked }
                    }
                  })}
                />
                <span className="toggle-switch"></span>
                <div>
                  <strong>RSI</strong>
                  <p>{indicatorInfo.rsi.description}</p>
                </div>
              </label>
            </div>
            {formData.indicators.rsi.enabled && (
              <div className="indicator-settings">
                <div className="setting-row">
                  <label>Перепроданность</label>
                  <input
                    type="number"
                    value={formData.indicators.rsi.oversold}
                    onChange={(e) => setFormData({
                      ...formData,
                      indicators: {
                        ...formData.indicators,
                        rsi: { ...formData.indicators.rsi, oversold: e.target.value }
                      }
                    })}
                    className="setting-input"
                  />
                </div>
                <div className="setting-row">
                  <label>Перекупленность</label>
                  <input
                    type="number"
                    value={formData.indicators.rsi.overbought}
                    onChange={(e) => setFormData({
                      ...formData,
                      indicators: {
                        ...formData.indicators,
                        rsi: { ...formData.indicators.rsi, overbought: e.target.value }
                      }
                    })}
                    className="setting-input"
                  />
                </div>
              </div>
            )}
          </div>

          {/* MACD */}
          <div className="indicator-item">
            <div className="indicator-header">
              <label className="indicator-toggle">
                <input
                  type="checkbox"
                  checked={formData.indicators.macd.enabled}
                  onChange={(e) => setFormData({
                    ...formData,
                    indicators: {
                      ...formData.indicators,
                      macd: { ...formData.indicators.macd, enabled: e.target.checked }
                    }
                  })}
                />
                <span className="toggle-switch"></span>
                <div>
                  <strong>MACD</strong>
                  <p>{indicatorInfo.macd.description}</p>
                </div>
              </label>
            </div>
            {formData.indicators.macd.enabled && (
              <div className="indicator-settings">
                <div className="setting-row">
                  <label>Быстрый период</label>
                  <input
                    type="number"
                    value={formData.indicators.macd.fastPeriod}
                    onChange={(e) => setFormData({
                      ...formData,
                      indicators: {
                        ...formData.indicators,
                        macd: { ...formData.indicators.macd, fastPeriod: e.target.value }
                      }
                    })}
                    className="setting-input"
                  />
                </div>
                <div className="setting-row">
                  <label>Медленный период</label>
                  <input
                    type="number"
                    value={formData.indicators.macd.slowPeriod}
                    onChange={(e) => setFormData({
                      ...formData,
                      indicators: {
                        ...formData.indicators,
                        macd: { ...formData.indicators.macd, slowPeriod: e.target.value }
                      }
                    })}
                    className="setting-input"
                  />
                </div>
                <div className="setting-row">
                  <label>Сигнальный период</label>
                  <input
                    type="number"
                    value={formData.indicators.macd.signalPeriod}
                    onChange={(e) => setFormData({
                      ...formData,
                      indicators: {
                        ...formData.indicators,
                        macd: { ...formData.indicators.macd, signalPeriod: e.target.value }
                      }
                    })}
                    className="setting-input"
                  />
                </div>
              </div>
            )}
          </div>

          {/* EMA */}
          <div className="indicator-item">
            <div className="indicator-header">
              <label className="indicator-toggle">
                <input
                  type="checkbox"
                  checked={formData.indicators.ema.enabled}
                  onChange={(e) => setFormData({
                    ...formData,
                    indicators: {
                      ...formData.indicators,
                      ema: { ...formData.indicators.ema, enabled: e.target.checked }
                    }
                  })}
                />
                <span className="toggle-switch"></span>
                <div>
                  <strong>EMA</strong>
                  <p>{indicatorInfo.ema.description}</p>
                </div>
              </label>
            </div>
            {formData.indicators.ema.enabled && (
              <div className="indicator-settings">
                <div className="setting-row">
                  <label>Короткий период</label>
                  <input
                    type="number"
                    value={formData.indicators.ema.shortPeriod}
                    onChange={(e) => setFormData({
                      ...formData,
                      indicators: {
                        ...formData.indicators,
                        ema: { ...formData.indicators.ema, shortPeriod: e.target.value }
                      }
                    })}
                    className="setting-input"
                  />
                </div>
                <div className="setting-row">
                  <label>Длинный период</label>
                  <input
                    type="number"
                    value={formData.indicators.ema.longPeriod}
                    onChange={(e) => setFormData({
                      ...formData,
                      indicators: {
                        ...formData.indicators,
                        ema: { ...formData.indicators.ema, longPeriod: e.target.value }
                      }
                    })}
                    className="setting-input"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Volume */}
          <div className="indicator-item">
            <div className="indicator-header">
              <label className="indicator-toggle">
                <input
                  type="checkbox"
                  checked={formData.indicators.volume.enabled}
                  onChange={(e) => setFormData({
                    ...formData,
                    indicators: {
                      ...formData.indicators,
                      volume: { ...formData.indicators.volume, enabled: e.target.checked }
                    }
                  })}
                />
                <span className="toggle-switch"></span>
                <div>
                  <strong>Объём</strong>
                  <p>{indicatorInfo.volume.description}</p>
                </div>
              </label>
            </div>
            {formData.indicators.volume.enabled && (
              <div className="indicator-settings">
                <div className="setting-row">
                  <label>Множитель объёма</label>
                  <input
                    type="number"
                    step="0.1"
                    value={formData.indicators.volume.multiplier}
                    onChange={(e) => setFormData({
                      ...formData,
                      indicators: {
                        ...formData.indicators,
                        volume: { ...formData.indicators.volume, multiplier: e.target.value }
                      }
                    })}
                    className="setting-input"
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );

  const renderStep4 = () => (
    <div className="step-content">
      <div className="step-header">
        <Target size={32} className="step-icon" />
        <h2>Выход из сделки</h2>
        <p>Настройте условия фиксации прибыли и ограничения убытков</p>
      </div>

      <div className="form-group">
        <label>
          Take Profit (%)
          <span className="tooltip-trigger" onMouseEnter={() => setShowIndicatorTooltip('tp')} onMouseLeave={() => setShowIndicatorTooltip(null)}>
            <Info size={14} />
          </span>
        </label>
        <input
          type="number"
          step="0.1"
          value={formData.takeProfit}
          onChange={(e) => setFormData({...formData, takeProfit: e.target.value})}
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
            onChange={(e) => setFormData({...formData, useStopLoss: e.target.checked})}
          />
          <span>Использовать Stop Loss</span>
          <span className="tooltip-trigger" onMouseEnter={() => setShowIndicatorTooltip('sl')} onMouseLeave={() => setShowIndicatorTooltip(null)}>
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
              onChange={(e) => setFormData({...formData, stopLoss: e.target.value})}
              placeholder="1.5"
              className="form-input"
            />
          </div>

          <div className="form-group">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={formData.trailingStop}
                onChange={(e) => setFormData({...formData, trailingStop: e.target.checked})}
              />
              <span>Трейлинг стоп</span>
              <span className="tooltip-trigger" onMouseEnter={() => setShowIndicatorTooltip('trailing')} onMouseLeave={() => setShowIndicatorTooltip(null)}>
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
          <strong>{formData.strategyPreset === 'custom' ? 'Своя' : strategyPresets[formData.strategyPreset]?.name}</strong>
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

          <div className="form-actions">
            {currentStep > 1 && (
              <button className="btn-secondary" onClick={handleBack}>
                Назад
              </button>
            )}
            {currentStep < 4 ? (
              <button className="btn-primary" onClick={handleNext}>
                Далее
                <ChevronRight size={20} />
              </button>
            ) : (
              <button className="btn-primary" onClick={handleSubmit}>
                <Bot size={20} />
                Создать бота
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CreateBotPage;