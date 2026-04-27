"use client"
import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Bot, Key, TrendingUp, TrendingDown, Settings, AlertCircle, Info, ChevronRight, ArrowLeft, Check, Target, Shield, Loader2, DollarSign } from 'lucide-react';
import { apiFetch, ApiError } from '@/lib/api';
import type { BotCreatePayload, FilterRule, Indicator, Timeframe } from '@/lib/types';
import './create-bot.css';

// Тип для API-ключа из БД
interface ApiKey {
  id: string;
  name: string;
  exchange: string;
}

const CreateBotPage = () => {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);
  const [formData, setFormData] = useState({
    // Шаг 1: Биржа, API ключ, депозит
    selectedApiKeyId: '',
    exchange: 'binance',
    stakeAmount: '100',           // USDT — сколько USDT выделено боту
    balanceRatio: '20',           // % от депозита на каждую сделку

    // Шаг 2: Торговая пара и плечо
    tradingPair: '',
    leverage: '3',
    algorithm: 'long', // long | short

    // Шаг 3: Индикаторы
    strategyPreset: 'custom', // conservative | moderate | aggressive | custom
    filters: [] as FilterRule[],

    // Шаг 4: Имя + выход из сделки
    botName: '',
    takeProfit: '2',
    stopLoss: '',
    useStopLoss: false,
    trailingStop: false,
  });

  // Список API-ключей из БД
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [apiKeysLoading, setApiKeysLoading] = useState(true);
  const [apiKeysError, setApiKeysError] = useState<string | null>(null);

  const [showIndicatorTooltip, setShowIndicatorTooltip] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Загружаем API-ключи при маунте
  useEffect(() => {
    const loadApiKeys = async () => {
      setApiKeysLoading(true);
      setApiKeysError(null);
      try {
        const data = await apiFetch<ApiKey[]>('/api-keys');
        setApiKeys(data);
        // Автовыбор первого ключа если список не пустой
        if (data.length > 0) {
          setFormData(prev => ({
            ...prev,
            selectedApiKeyId: data[0].id,
            exchange: data[0].exchange,
          }));
        }
      } catch (err) {
        setApiKeysError('Не удалось загрузить API-ключи');
      } finally {
        setApiKeysLoading(false);
      }
    };
    loadApiKeys();
  }, []);

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

  // Когда меняется выбранный ключ — синхронизируем exchange
  const handleApiKeyChange = (keyId: string) => {
    const found = apiKeys.find(k => k.id === keyId);
    setFormData({
      ...formData,
      selectedApiKeyId: keyId,
      exchange: found ? found.exchange : formData.exchange,
    });
  };

  const handleNext = () => {
    if (currentStep === 1) {
      if (!formData.selectedApiKeyId) {
        setSubmitError('Выберите API-ключ');
        return;
      }
      if (!formData.stakeAmount || Number(formData.stakeAmount) <= 0) {
        setSubmitError('Укажите депозит больше 0');
        return;
      }
    }
    setSubmitError(null);
    if (currentStep < 4) setCurrentStep(currentStep + 1);
  };

  const handleBack = () => {
    setSubmitError(null);
    if (currentStep > 1) setCurrentStep(currentStep - 1);
  };

  // "BTC/USDT" → "BTC/USDT:USDT"
  const toFuturesPair = (raw: string): string => {
    const trimmed = raw.trim().toUpperCase();
    if (trimmed.includes(':')) return trimmed;
    return `${trimmed}:USDT`;
  };

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
      // Новые поля
      api_key_id: formData.selectedApiKeyId,
      stake_amount: Number(formData.stakeAmount),
      tradable_balance_ratio: Number(formData.balanceRatio) / 100,
    };

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
            {step === 1 && 'Биржа и депозит'}
            {step === 2 && 'Пара и плечо'}
            {step === 3 && 'Стратегия'}
            {step === 4 && 'Имя и TP/SL'}
          </div>
        </div>
      ))}
    </div>
  );

  const renderStep1 = () => {
    const selectedKey = apiKeys.find(k => k.id === formData.selectedApiKeyId);
    const stakeNum = Number(formData.stakeAmount) || 0;
    const ratioNum = Number(formData.balanceRatio) || 0;
    const perTradeUsdt = stakeNum * (ratioNum / 100);

    return (
      <div className="step-content">
        <div className="step-header">
          <Key size={32} className="step-icon" />
          <h2>Биржа и депозит</h2>
          <p>Выберите API-ключ и укажите, сколько средств выделить боту</p>
        </div>

        {/* API-ключ */}
        <div className="form-group">
          <label>
            API-ключ
            <span
              className="tooltip-trigger"
              onMouseEnter={() => setShowIndicatorTooltip('apiKey')}
              onMouseLeave={() => setShowIndicatorTooltip(null)}
            >
              <Info size={14} />
            </span>
          </label>

          {apiKeysLoading ? (
            <div className="api-keys-loading">
              <Loader2 size={18} className="spin" />
              <span>Загрузка ключей...</span>
            </div>
          ) : apiKeysError ? (
            <div className="warning-banner">
              <AlertCircle size={16} />
              <span>{apiKeysError}</span>
            </div>
          ) : apiKeys.length === 0 ? (
            <div className="info-banner">
              <AlertCircle size={18} />
              <div>
                <strong>Нет сохранённых ключей.</strong>{' '}
                <a href="/settings/api-keys" className="link">
                  Добавьте API-ключ в настройках
                </a>
              </div>
            </div>
          ) : (
            <select
              value={formData.selectedApiKeyId}
              onChange={(e) => handleApiKeyChange(e.target.value)}
              className="form-select"
            >
              {apiKeys.map((key) => (
                <option key={key.id} value={key.id}>
                  {key.name} ({key.exchange.toUpperCase()})
                </option>
              ))}
            </select>
          )}

          {showIndicatorTooltip === 'apiKey' && (
            <div className="tooltip">
              Ключи добавляются в Настройки → API-ключи
            </div>
          )}

          {/* Показываем биржу выбранного ключа */}
          {selectedKey && (
            <div className="field-hint">
              Биржа: <strong>{selectedKey.exchange.toUpperCase()}</strong>
            </div>
          )}
        </div>

        {/* Депозит бота */}
        <div className="form-group">
          <label>
            Депозит бота (USDT)
            <span
              className="tooltip-trigger"
              onMouseEnter={() => setShowIndicatorTooltip('stake')}
              onMouseLeave={() => setShowIndicatorTooltip(null)}
            >
              <Info size={14} />
            </span>
          </label>
          <div className="input-with-suffix">
            <input
              type="number"
              min="1"
              step="10"
              value={formData.stakeAmount}
              onChange={(e) => setFormData({ ...formData, stakeAmount: e.target.value })}
              placeholder="100"
              className="form-input"
            />
            <span className="input-suffix">USDT</span>
          </div>
          {showIndicatorTooltip === 'stake' && (
            <div className="tooltip">
              Общая сумма, которую бот может использовать для торговли
            </div>
          )}
        </div>

        {/* Процент от депозита на сделку */}
        <div className="form-group">
          <label>
            Размер одной сделки — {formData.balanceRatio}% от депозита
            <span
              className="tooltip-trigger"
              onMouseEnter={() => setShowIndicatorTooltip('ratio')}
              onMouseLeave={() => setShowIndicatorTooltip(null)}
            >
              <Info size={14} />
            </span>
          </label>
          <div className="leverage-selector">
            <input
              type="range"
              min="5"
              max="100"
              step="5"
              value={formData.balanceRatio}
              onChange={(e) => setFormData({ ...formData, balanceRatio: e.target.value })}
              className="leverage-slider"
            />
            <div className="leverage-value">{formData.balanceRatio}%</div>
          </div>
          {showIndicatorTooltip === 'ratio' && (
            <div className="tooltip">
              Какую долю депозита бот использует в каждой сделке. Меньше % — меньше риск.
            </div>
          )}
        </div>

        {/* Информационная карточка */}
        {stakeNum > 0 && (
          <div className="summary-card">
            <div className="summary-row">
              <span>Депозит бота:</span>
              <strong>{stakeNum} USDT</strong>
            </div>
            <div className="summary-row">
              <span>На каждую сделку:</span>
              <strong className="profit-text">
                {perTradeUsdt.toFixed(2)} USDT ({formData.balanceRatio}%)
              </strong>
            </div>
            <div className="summary-row">
              <span>Максимальных сделок одновременно:</span>
              <strong>{ratioNum > 0 ? Math.floor(100 / ratioNum) : '—'}</strong>
            </div>
          </div>
        )}

        <div className="info-banner">
          <AlertCircle size={18} />
          <div>
            <strong>Режим тестирования (dry-run):</strong> реальные деньги не используются.
            API-ключ потребуется при переходе в боевой режим.
          </div>
        </div>
      </div>
    );
  };

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

  const renderStep4 = () => {
    const selectedKey = apiKeys.find(k => k.id === formData.selectedApiKeyId);
    return (
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
            <span>API-ключ:</span>
            <strong>{selectedKey ? `${selectedKey.name} (${selectedKey.exchange.toUpperCase()})` : '—'}</strong>
          </div>
          <div className="summary-row">
            <span>Депозит бота:</span>
            <strong>{formData.stakeAmount} USDT</strong>
          </div>
          <div className="summary-row">
            <span>Размер сделки:</span>
            <strong>{formData.balanceRatio}% ({(Number(formData.stakeAmount) * Number(formData.balanceRatio) / 100).toFixed(2)} USDT)</strong>
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
  };

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

          {submitError && (
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
              <button
                className="btn-primary"
                onClick={handleNext}
                disabled={currentStep === 1 && apiKeysLoading}
              >
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