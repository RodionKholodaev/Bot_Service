'use client';
import React, { useCallback, useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Bot,
  Key,
  TrendingUp,
  TrendingDown,
  Settings,
  AlertCircle,
  Info,
  ChevronRight,
  ArrowLeft,
  Check,
  Target,
  Shield,
  Loader2,
  DollarSign,
  Calculator,
} from 'lucide-react';
import { apiFetch, ApiError } from '@/lib/api';
import {
  MIN_SERVICE_BALANCE_RUB,
  INDICATOR_META,
  INDICATOR_KEYS,
} from '@/lib/constants';
import type {
  BotCreatePayload,
  FilterRule,
  Indicator,
  StrategyPreset,
  StrategyPresetOut,
  Timeframe,
} from '@/lib/types';
import { AssistantLauncher } from './assistant/AssistantLauncher';
import { AssistantPanel } from './assistant/AssistantPanel';
import { fetchAssistantStatus } from './assistant/assistantApi';
import {
  applySuggestionsToForm,
  toSnapshot,
  type BotFormValues,
} from './assistant/applySuggestions';
import { firstStepOf } from './assistant/fieldMeta';
import {
  computeTradeMath,
  collectTradeWarnings,
  parsePositiveNumber,
} from './tradeMath';
import type { Suggestion } from './assistant/types';
import './create-bot.css';
import './assistant/assistant.css';
import { SiteFooter } from '@/app/components/SiteFooter';

// Тип для API-ключа из БД
interface ApiKey {
  id: string;
  name: string;
  exchange: string;
}

// Свободный капитал ключа: баланс на бирже минус депозиты уже созданных на нём
// ботов. Тот же расчёт отбивает создание бота на бэкенде (409) — здесь он нужен,
// чтобы человек увидел лимит, пока вводит депозит, а не отказом на последнем шаге.
interface KeyBalance {
  total: number;
  free: number;
  reserved: number;
  available: number;
  bots: { id: string; name: string; stake_amount: number }[];
}

// 40 -> "40", 12.55 -> "12.55": цифры баланса читает человек, хвост из нулей мешает
const formatUsdt = (value: number) =>
  Number(value.toFixed(2)).toLocaleString('ru-RU');

// Иконка и цвет карточки пресета — единственное, что фронт про пресеты знает сам:
// React-компонент бэкенду не сериализовать. Всё остальное (условия входа, TP, SL)
// приходит из GET /bots/presets. Незнакомый ключ рисуется дефолтом, а не роняет форму.
const PRESET_VISUALS: Record<
  string,
  {
    icon: React.ComponentType<{ size?: number; style?: React.CSSProperties }>;
    color: string;
  }
> = {
  conservative: { icon: Shield, color: '#10b981' },
  moderate: { icon: TrendingUp, color: '#60a5fa' },
  aggressive: { icon: Target, color: '#f59e0b' },
};

const DEFAULT_PRESET_VISUAL = { icon: Settings, color: '#8b5cf6' };

// кастомный select для выбора индикаторов (чтобы нормально выглядело))
const CustomSelect = ({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (val: string) => void;
  options: { value: string; label: string }[];
}) => {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);
  const label = options.find((o) => o.value === value)?.label ?? value;

  React.useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div
      ref={ref}
      className="custom-select filter-select"
      onClick={() => setOpen((o) => !o)}
    >
      <span>{label}</span>
      <ChevronRight
        size={14}
        style={{
          transform: open ? 'rotate(90deg)' : 'rotate(0deg)',
          transition: '0.2s',
        }}
      />
      {open && (
        <div className="custom-select-dropdown">
          {options.map((opt) => (
            <div
              key={opt.value}
              className={`custom-select-option ${opt.value === value ? 'active' : ''}`}
              onClick={(e) => {
                e.stopPropagation();
                onChange(opt.value);
                setOpen(false);
              }}
            >
              {opt.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const CreateBotPage = () => {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);
  const [formData, setFormData] = useState<BotFormValues>({
    // Шаг 1: Биржа, API ключ, депозит
    selectedApiKeyId: '',
    exchange: 'binance',
    stakeAmount: '100', // USDT — сколько USDT выделено боту
    balanceRatio: '20', // % от депозита на каждую сделку

    // Шаг 2: Торговая пара и плечо
    tradingPair: '',
    leverage: '3',
    algorithm: 'long', // long | short

    // Шаг 3: Индикаторы
    strategyPreset: 'custom', // conservative | moderate | aggressive | custom
    filters: [],

    // Шаг 4: Имя + выход из сделки
    botName: '',
    // Проценты — движение цены. Прежние дефолты (TP 2 / SL 1.5) читались как доли маржи
    // и при плече x3 значили 0.67% и 0.5% хода цены; в новой трактовке те же цифры дали
    // бы втрое большие цели, поэтому числа пересмотрены.
    takeProfit: '1',
    stopLoss: '',
    useStopLoss: false,
    dryRun: true,
  });

  // Готовые стратегии с бэкенда. Своей копии наборов у формы больше нет: пока она
  // была, бот, созданный запросом POST /bots с тем же именем пресета, отличался от
  // того, что рисовал интерфейс.
  const [presets, setPresets] = useState<Record<string, StrategyPresetOut>>({});
  const [presetsLoading, setPresetsLoading] = useState(true);

  // Список API-ключей из БД
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [apiKeysLoading, setApiKeysLoading] = useState(true);
  const [apiKeysError, setApiKeysError] = useState<string | null>(null);

  // Капитал выбранного ключа вместе с id ключа, для которого он посчитан: без id
  // при переключении ключа секунду показывались бы чужие цифры. null — ещё не
  // спрашивали или биржа не ответила; тогда ничего не показываем и ничего не
  // блокируем — решение всё равно за бэкендом, а он спросит биржу заново.
  const [keyBalance, setKeyBalance] = useState<{
    keyId: string;
    data: KeyBalance;
  } | null>(null);

  const [showIndicatorTooltip, setShowIndicatorTooltip] = useState<
    string | null
  >(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Сервисный баланс: ниже порога бэкенд не даст создать боевого бота (402), см.
  // backend/src/services/balance_guard.py. null — ещё не загрузили; пока не знаем,
  // ничего не блокируем.
  const [serviceBalance, setServiceBalance] = useState<number | null>(null);

  // ИИ-помощник: панель справа. assistantEnabled приходит с бэкенда —
  // если ключ AITunnel не настроен, ничего не показываем.
  const [assistantEnabled, setAssistantEnabled] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);

  // проверка того что пользователь имеет JWT
  useEffect(() => {
    if (!localStorage.getItem('access_token')) {
      router.replace('/auth');
    }
  }, [router]);

  // Загружаем API-ключи при маунте — без автовыбора,
  // чтобы не засорять selectedApiKeyId в dry-run режиме.
  useEffect(() => {
    if (!localStorage.getItem('access_token')) return;
    const loadApiKeys = async () => {
      setApiKeysLoading(true);
      setApiKeysError(null);
      try {
        const data = await apiFetch<ApiKey[]>('/api/api-keys');
        setApiKeys(data);
        // Автовыбор только если уже стоит боевой режим
        // (по умолчанию dryRun=true, поэтому здесь ключ НЕ выбираем)
      } catch (err) {
        setApiKeysError(
          'Не удалось загрузить API-ключи. Добавьте их в настройках',
        );
      } finally {
        setApiKeysLoading(false);
      }
    };
    loadApiKeys();
  }, []);

  // Состояние трогаем в .then/.catch, а не синхронно в эффекте — так же, как с
  // балансом ниже: синхронный setState внутри эффекта запрещён линтом.
  useEffect(() => {
    if (!localStorage.getItem('access_token')) return;
    apiFetch<StrategyPresetOut[]>('/bots/presets')
      .then((list) => {
        setPresets(Object.fromEntries(list.map((p) => [p.key, p])));
        setPresetsLoading(false);
      })
      .catch(() => setPresetsLoading(false));
  }, []);

  // Баланс ключа спрашиваем только в боевом режиме и только по выбранному ключу:
  // этот запрос ходит на биржу, дёргать его на каждый ключ в списке ни к чему.
  // Состояние трогаем строго в .then/.catch: синхронный setState внутри эффекта
  // запрещён правилом react-hooks/set-state-in-effect (жёсткий гейт линта), а
  // устаревшие цифры отсекаются сравнением keyId при отображении.
  useEffect(() => {
    if (!localStorage.getItem('access_token')) return;
    if (formData.dryRun || !formData.selectedApiKeyId) return;

    const keyId = formData.selectedApiKeyId;
    let cancelled = false;
    apiFetch<KeyBalance>(`/api/api-keys/${keyId}/balance`)
      .then((data) => {
        if (!cancelled) setKeyBalance({ keyId, data });
      })
      .catch(() => {
        if (!cancelled) setKeyBalance(null);
      });

    return () => {
      cancelled = true;
    };
  }, [formData.dryRun, formData.selectedApiKeyId]);

  useEffect(() => {
    if (!localStorage.getItem('access_token')) return;
    apiFetch<{ service_balance: number }>('/users/me/balance')
      .then((data) => setServiceBalance(data.service_balance))
      .catch(() => setServiceBalance(null));
  }, []);

  useEffect(() => {
    if (!localStorage.getItem('access_token')) return;
    fetchAssistantStatus()
      .then((status) => setAssistantEnabled(status.enabled))
      .catch(() => setAssistantEnabled(false));
  }, []);

  // Цифры показываем, только если они посчитаны для сейчас выбранного ключа и
  // режим боевой: в dry-run биржевого счёта у бота нет вовсе.
  const keyCapital =
    !formData.dryRun &&
    keyBalance &&
    keyBalance.keyId === formData.selectedApiKeyId
      ? keyBalance.data
      : null;

  // Боевого бота при таком балансе создать нельзя; dry-run порог не ограничивает —
  // за него комиссия не берётся.
  const liveBotBlocked =
    serviceBalance !== null &&
    serviceBalance < MIN_SERVICE_BALANCE_RUB &&
    !formData.dryRun;

  // Ассистент читает форму в момент отправки вопроса, а не при рендере
  const getAssistantSnapshot = useCallback(
    () => toSnapshot(formData, currentStep, apiKeys.length > 0),
    [formData, currentStep, apiKeys.length],
  );

  // Пользователь нажал «Применить» в ответе ассистента
  const handleApplySuggestions = useCallback(
    (suggestions: Suggestion[]) => {
      setFormData((prev) =>
        applySuggestionsToForm(prev, suggestions, apiKeys[0]),
      );
      setSubmitError(null);
      // Переводим на шаг, где изменённое поле видно — иначе непонятно, что произошло
      setCurrentStep(firstStepOf(suggestions));
    },
    [apiKeys],
  );

  useEffect(() => {
    if (formData.strategyPreset === 'custom') return;
    const preset = presets[formData.strategyPreset];
    if (!preset) return;
    // Эффект нарочно: значения пресета подставляются не только по клику (для этого
    // есть handlePresetSelect), но и когда strategyPreset меняет ИИ-ассистент
    // (см. applySuggestionsToForm) или когда пресеты доехали с бэкенда позже выбора.
    // Перенести в обработчики нельзя, не потеряв эти пути.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFormData((prev) => ({
      ...prev,
      filters:
        prev.algorithm === 'long' ? preset.long_filters : preset.short_filters,
      takeProfit: String(preset.take_profit_percent),
      stopLoss:
        preset.stop_loss_percent === null
          ? ''
          : String(preset.stop_loss_percent),
      useStopLoss: preset.stop_loss_enabled,
    }));
  }, [formData.algorithm, formData.strategyPreset, presets]);

  const popularPairs = [
    'BTC/USDT',
    'ETH/USDT',
    'BNB/USDT',
    'SOL/USDT',
    'XRP/USDT',
    'ADA/USDT',
    'DOGE/USDT',
    'AVAX/USDT',
  ];

  const handlePresetSelect = (key: string) => {
    const preset = presets[key];
    if (!preset) return;
    setFormData({
      ...formData,
      strategyPreset: key,
      filters:
        formData.algorithm === 'long'
          ? preset.long_filters
          : preset.short_filters,
      takeProfit: String(preset.take_profit_percent),
      stopLoss:
        preset.stop_loss_percent === null
          ? ''
          : String(preset.stop_loss_percent),
      useStopLoss: preset.stop_loss_enabled,
    });
  };

  // Любая ручная правка условий переводит стратегию в «Свои настройки». Иначе в базу
  // уехало бы имя пресета, под которым лежат уже другие условия, — и сравнивать
  // пресеты между собой было бы не с чем.
  const setFilters = (filters: FilterRule[]) =>
    setFormData((prev) => ({ ...prev, filters, strategyPreset: 'custom' }));

  // Когда меняется выбранный ключ — синхронизируем exchange
  const handleApiKeyChange = (keyId: string) => {
    const found = apiKeys.find((k) => k.id === keyId);
    setFormData((prev) => ({
      ...prev,
      selectedApiKeyId: keyId,
      exchange: found ? found.exchange : prev.exchange,
    }));
  };

  // Переключение режима торговли:
  // dry-run → очищаем ключ; боевой → подставляем первый доступный ключ
  const handleDryRunToggle = (isDryRun: boolean) => {
    if (isDryRun) {
      setFormData((prev) => ({
        ...prev,
        dryRun: true,
        selectedApiKeyId: '',
        exchange: 'bybit',
      }));
    } else {
      const firstKey = apiKeys[0];
      setFormData((prev) => ({
        ...prev,
        dryRun: false,
        selectedApiKeyId: firstKey?.id ?? '',
        exchange: firstKey?.exchange ?? prev.exchange,
      }));
    }
  };

  const handleNext = () => {
    if (currentStep === 1) {
      if (!formData.dryRun && !formData.selectedApiKeyId) {
        setSubmitError('Выберите API-ключ');
        return;
      }
      if (!formData.stakeAmount || Number(formData.stakeAmount) <= 0) {
        setSubmitError('Укажите депозит больше 0');
        return;
      }
      // Тот же отказ придёт с бэкенда (409), но лучше сказать об этом здесь, чем
      // после четырёх шагов формы. Если баланс не загрузился — не мешаем.
      if (keyCapital && Number(formData.stakeAmount) > keyCapital.available) {
        setSubmitError(
          `На ключе свободно ${formatUsdt(keyCapital.available)} USDT` +
            (keyCapital.reserved > 0
              ? ` (${formatUsdt(keyCapital.reserved)} занято другими ботами)`
              : '') +
            '. Уменьшите депозит или пополните счёт на бирже.',
        );
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
    if (
      formData.useStopLoss &&
      (!formData.stopLoss || Number(formData.stopLoss) <= 0)
    )
      return 'Укажите Stop Loss больше 0';
    if (formData.strategyPreset === 'custom') {
      if (formData.filters.length === 0)
        return 'Добавьте хотя бы один индикатор';
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
      // Настоящий выбор человека, а не литерал: раньше у всех ботов, созданных
      // через форму, в базе оказывался «custom».
      strategy_preset: formData.strategyPreset as StrategyPreset,
      take_profit_percent: Number(formData.takeProfit),
      stop_loss_enabled: formData.useStopLoss,
      stop_loss_percent: formData.useStopLoss
        ? Number(formData.stopLoss)
        : null,
      dry_run: formData.dryRun,
      // FIX: api_key_id отправляется только в боевом режиме
      api_key_id:
        !formData.dryRun && formData.selectedApiKeyId
          ? Number(formData.selectedApiKeyId)
          : null,
      stake_amount: Number(formData.stakeAmount),
      tradable_balance_ratio: Number(formData.balanceRatio) / 100,
    };

    if (direction === 'long') {
      payload.entry_filters_long = formData.filters;
    }
    if (direction === 'short') {
      payload.entry_filters_short = formData.filters;
    }

    console.log('Настройки бота:', JSON.stringify(payload, null, 2));

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
    const selectedKey = apiKeys.find((k) => k.id === formData.selectedApiKeyId);
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

        {/* Режим торговли */}
        <div className="form-group">
          <label>Режим торговли</label>
          <div className="trading-mode-toggle">
            <button
              type="button"
              className={`mode-btn ${formData.dryRun ? 'mode-btn--active mode-btn--dry' : ''}`}
              onClick={() => handleDryRunToggle(true)}
            >
              🧪 Dry Run
              <span className="mode-desc">
                Тестовый режим — без реальных денег
              </span>
            </button>
            <button
              type="button"
              className={`mode-btn ${!formData.dryRun ? 'mode-btn--active mode-btn--live' : ''}`}
              onClick={() => handleDryRunToggle(false)}
            >
              🔴 Боевой
              <span className="mode-desc">Реальная торговля</span>
            </button>
          </div>
          {!formData.dryRun && (
            <div className="warning-banner" style={{ marginTop: 8 }}>
              <AlertCircle size={16} />
              <span>Внимание: бот будет торговать реальными средствами</span>
            </div>
          )}
          {liveBotBlocked && (
            <div className="warning-banner" style={{ marginTop: 8 }}>
              <AlertCircle size={16} />
              <span>
                Баланс сервиса ниже {MIN_SERVICE_BALANCE_RUB} ₽ — боевого бота
                создать нельзя. Пополните баланс или выберите тестовый режим.
              </span>
            </div>
          )}
        </div>

        {/* API-ключ — показывается только в боевом режиме */}
        {!formData.dryRun && (
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
                  <Link href="/settings" className="link">
                    Добавьте API-ключ в настройках
                  </Link>
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
        )}

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
              onChange={(e) =>
                setFormData({ ...formData, stakeAmount: e.target.value })
              }
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
          {/* Депозиты всех ботов на одном ключе берутся из одного кошелька:
              изолированная маржа разводит риск по позициям, но не деньги. */}
          {keyCapital && (
            <div
              className={
                Number(formData.stakeAmount) > keyCapital.available
                  ? 'field-hint field-hint--warning'
                  : 'field-hint'
              }
            >
              Свободно на ключе {formatUsdt(keyCapital.available)} USDT из{' '}
              {formatUsdt(keyCapital.total)}
              {keyCapital.reserved > 0 && (
                <>
                  {' '}
                  — {formatUsdt(keyCapital.reserved)} уже занято:{' '}
                  {keyCapital.bots
                    .map(
                      (bot) =>
                        `${bot.name} (${formatUsdt(bot.stake_amount)} USDT)`,
                    )
                    .join(', ')}
                </>
              )}
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
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  balanceRatio: e.target.value,
                }))
              }
              className="leverage-slider"
            />
            <div className="leverage-value">{formData.balanceRatio}%</div>
          </div>
          {showIndicatorTooltip === 'ratio' && (
            <div className="tooltip">
              Какую долю депозита бот использует в каждой сделке. Меньше % —
              меньше риск.
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
              <span>На сделку:</span>
              <strong className="profit-text">
                {perTradeUsdt.toFixed(2)} USDT ({formData.balanceRatio}%)
              </strong>
            </div>
          </div>
        )}
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
            setFormData({
              ...formData,
              tradingPair: e.target.value.toUpperCase(),
            })
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
            onChange={(e) =>
              setFormData({ ...formData, leverage: e.target.value })
            }
            className="leverage-slider"
          />
          <div className="leverage-value">x{formData.leverage}</div>
        </div>
        {showIndicatorTooltip === 'leverage' && (
          <div className="tooltip">
            Плечо увеличивает потенциальную прибыль и риск. Новичкам
            рекомендуется x1-x3
          </div>
        )}
        {parseInt(formData.leverage) > 5 && (
          <div className="warning-banner">
            <AlertCircle size={16} />
            <span>
              Высокое плечо увеличивает риск ликвидации. Будьте осторожны!
            </span>
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

  const renderStep3 = () => {
    // Справка показывается только по индикаторам, которые реально стоят в условиях:
    // шкалы у них разные, и «Bollinger %B меньше 20» без пояснения ничего не говорит.
    const usedIndicators = INDICATOR_KEYS.filter((key) =>
      formData.filters.some((f) => f.indicator === key),
    );

    return (
      <div className="step-content">
        <div className="step-header">
          <Settings size={32} className="step-icon" />
          <h2>Стратегия входа</h2>
          <p>Выберите готовую стратегию или настройте индикаторы вручную</p>
        </div>

        <div className="preset-selector">
          {Object.values(presets).map((preset) => {
            const visual = PRESET_VISUALS[preset.key] ?? DEFAULT_PRESET_VISUAL;
            const Icon = visual.icon;
            const active = formData.strategyPreset === preset.key;
            return (
              <button
                key={preset.key}
                className={`preset-card ${active ? 'active' : ''}`}
                onClick={() => handlePresetSelect(preset.key)}
                style={active ? { borderColor: visual.color } : {}}
              >
                <Icon size={24} style={{ color: visual.color }} />
                <strong>{preset.name}</strong>
                <span>{preset.description}</span>
              </button>
            );
          })}
          <button
            className={`preset-card ${formData.strategyPreset === 'custom' ? 'active' : ''}`}
            onClick={() =>
              setFormData({ ...formData, strategyPreset: 'custom' })
            }
          >
            <Settings size={24} style={{ color: '#8b5cf6' }} />
            <strong>Свои настройки</strong>
            <span>Настроить вручную</span>
          </button>
        </div>

        {/* Готовые стратегии живут на бэкенде. Пока не доехали — показываем это, а не
          пустое место: ручная настройка работает в любом случае. */}
        {presetsLoading && (
          <p className="preset-hint">Загружаем готовые стратегии…</p>
        )}
        {!presetsLoading && Object.keys(presets).length === 0 && (
          <p className="preset-hint">
            Не удалось загрузить готовые стратегии — настройте условия входа
            вручную.
          </p>
        )}

        <div className="indicators-config">
          <h3>Индикаторы входа</h3>

          {formData.filters.map((filter, idx) => (
            <div key={idx} className="filter-row">
              <CustomSelect
                value={filter.indicator}
                onChange={(val) => {
                  const indicator = val as Indicator;
                  const updated = [...formData.filters];
                  // Значение сбрасывается на типичное для нового индикатора: шкалы разные
                  // (RSI 0–100, CCI ±200), и оставленное от прежнего число почти всегда
                  // означает не то, что человек имел в виду.
                  updated[idx] = {
                    ...updated[idx],
                    indicator,
                    value: INDICATOR_META[indicator].defaultValue,
                  };
                  setFilters(updated);
                }}
                options={INDICATOR_KEYS.map((key) => ({
                  value: key,
                  label: INDICATOR_META[key].label,
                }))}
              />

              <CustomSelect
                value={filter.timeframe}
                onChange={(val) => {
                  const updated = [...formData.filters];
                  updated[idx] = {
                    ...updated[idx],
                    timeframe: val as Timeframe,
                  };
                  setFilters(updated);
                }}
                options={[
                  { value: '1m', label: '1m' },
                  { value: '5m', label: '5m' },
                  { value: '15m', label: '15m' },
                  { value: '30m', label: '30m' },
                  { value: '1h', label: '1h' },
                  { value: '4h', label: '4h' },
                ]}
              />

              <CustomSelect
                value={filter.condition}
                onChange={(val) => {
                  const updated = [...formData.filters];
                  updated[idx] = {
                    ...updated[idx],
                    condition: val as FilterRule['condition'],
                  };
                  setFilters(updated);
                }}
                options={[
                  { value: 'less', label: '< меньше' },
                  { value: 'greater', label: '> больше' },
                ]}
              />

              <input
                type="number"
                value={filter.value}
                onChange={(e) => {
                  const updated = [...formData.filters];
                  updated[idx] = {
                    ...updated[idx],
                    value: Number(e.target.value),
                  };
                  setFilters(updated);
                }}
                className="form-input filter-input"
                placeholder={
                  INDICATOR_META[filter.indicator]?.placeholder ?? ''
                }
              />

              <button
                className="filter-remove-btn"
                onClick={() =>
                  setFilters(formData.filters.filter((_, i) => i !== idx))
                }
              >
                ✕
              </button>
            </div>
          ))}

          <button
            className="filter-add-btn"
            onClick={() =>
              setFilters([
                ...formData.filters,
                {
                  indicator: 'rsi' as Indicator,
                  timeframe: '5m' as Timeframe,
                  condition: 'less',
                  value: INDICATOR_META.rsi.defaultValue,
                },
              ])
            }
          >
            <span>＋</span> Добавить индикатор
          </button>

          {usedIndicators.length > 0 && (
            <div className="indicator-legend">
              {usedIndicators.map((key) => (
                <p className="indicator-legend-item" key={key}>
                  <strong>{INDICATOR_META[key].name}</strong>, период{' '}
                  {INDICATOR_META[key].period}.{' '}
                  {INDICATOR_META[key].description}
                </p>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderStep4 = () => {
    // FIX: selectedKey ищем только если не dry-run
    const selectedKey = !formData.dryRun
      ? apiKeys.find((k) => k.id === formData.selectedApiKeyId)
      : undefined;

    // Что настройки значат на самом деле. Считается прямо при рендере: любая правка
    // take profit, стопа или плеча перерисовывает шаг и пересчитывает эти числа сама,
    // без состояния и без эффекта.
    const tradeMargin =
      (Number(formData.stakeAmount) * Number(formData.balanceRatio)) / 100;
    const tradeSettings = {
      takeProfitPercent: parsePositiveNumber(formData.takeProfit) ?? 0,
      stopLossPercent: formData.useStopLoss
        ? parsePositiveNumber(formData.stopLoss)
        : null,
      leverage: Number(formData.leverage),
      marginUsdt:
        Number.isFinite(tradeMargin) && tradeMargin > 0 ? tradeMargin : 0,
    };
    const tradeMath = computeTradeMath(tradeSettings);
    const tradeWarnings = tradeMath
      ? collectTradeWarnings(tradeMath, tradeSettings)
      : [];

    return (
      <div className="step-content">
        <div className="step-header">
          <Target size={32} className="step-icon" />
          <h2>Имя и выход из сделки</h2>
          <p>
            Дайте боту имя и настройте условия фиксации прибыли и ограничения
            убытков
          </p>
        </div>

        <div className="form-group">
          <label>Имя бота</label>
          <input
            type="text"
            value={formData.botName}
            onChange={(e) =>
              setFormData({ ...formData, botName: e.target.value })
            }
            placeholder="Например: BTC скальпер"
            maxLength={100}
            className="form-input"
          />
        </div>

        <div className="form-group">
          <label>
            Take Profit — движение цены (%)
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
            onChange={(e) =>
              setFormData({ ...formData, takeProfit: e.target.value })
            }
            placeholder="1.0"
            className="form-input"
          />
          {showIndicatorTooltip === 'tp' && (
            <div className="tooltip">
              На сколько процентов должна пройти цена, чтобы бот закрыл сделку в
              плюс. Плечо на эту величину не влияет — оно умножает результат, а
              не приближает цель.
            </div>
          )}
        </div>

        <div className="form-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={formData.useStopLoss}
              onChange={(e) =>
                setFormData({ ...formData, useStopLoss: e.target.checked })
              }
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
              Закрывает сделку, когда цена прошла заданный процент против вас.
              Без стопа позиция держится до ликвидации.
            </div>
          )}
        </div>

        {formData.useStopLoss && (
          <div className="form-group">
            <label>Stop Loss — движение цены (%)</label>
            <input
              type="number"
              step="0.1"
              value={formData.stopLoss}
              onChange={(e) =>
                setFormData({ ...formData, stopLoss: e.target.value })
              }
              placeholder="0.5"
              className="form-input"
            />
          </div>
        )}

        <div className="reality-card">
          <h3>
            <Calculator size={16} />
            Что это значит на самом деле
          </h3>

          {tradeMath ? (
            <>
              <div className="summary-row">
                <span>Прибыль по take profit:</span>
                <strong className="profit-text">
                  +{tradeMath.profitMarginPercent.toFixed(1)}% депозита сделки
                  {tradeSettings.marginUsdt > 0 &&
                    ` (+${tradeMath.profitUsdt.toFixed(2)} USDT)`}
                </strong>
              </div>

              <div className="summary-row">
                <span>
                  {tradeMath.hasStopLoss
                    ? 'Убыток по стопу:'
                    : 'Убыток без стопа:'}
                </span>
                <strong className="loss-text">
                  −{tradeMath.lossMarginPercent.toFixed(1)}% депозита сделки
                  {tradeSettings.marginUsdt > 0 &&
                    ` (−${tradeMath.lossUsdt.toFixed(2)} USDT)`}
                </strong>
              </div>

              <div className="summary-row">
                <span>Комиссия биржи за круг:</span>
                <strong>
                  {tradeMath.feePricePercent}% цены (
                  {tradeMath.feeMarginPercent.toFixed(2)}% депозита сделки)
                </strong>
              </div>

              <div className="summary-row">
                <span>Движение цены до take profit:</span>
                <strong>
                  {tradeMath.effectiveTakeProfitPricePercent.toFixed(2)}%
                </strong>
              </div>

              {tradeMath.hasStopLoss && (
                <div className="summary-row">
                  <span>Стоп с учётом комиссии:</span>
                  <strong>
                    {tradeMath.effectiveStopPricePercent.toFixed(2)}% движения
                    цены
                  </strong>
                </div>
              )}

              <div className="summary-row">
                <span>Нужный винрейт, чтобы выйти в ноль:</span>
                <strong>{Math.round(tradeMath.requiredWinrate)} из 100</strong>
              </div>

              {tradeSettings.leverage > 1 && (
                <div className="summary-row">
                  <span>Ликвидация примерно при:</span>
                  <strong>
                    {tradeMath.liquidationPricePercent.toFixed(1)}% движения
                    цены
                  </strong>
                </div>
              )}

              <p className="reality-note">
                Плечо x{formData.leverage} не приближает take profit: цене всё
                равно нужно пройти {tradeSettings.takeProfitPercent}%. Оно
                умножает и прибыль, и убыток — и приближает ликвидацию.
              </p>
            </>
          ) : (
            <p className="reality-note">
              Укажите take profit, чтобы увидеть расчёт.
            </p>
          )}
        </div>

        {tradeWarnings.map((warning) => (
          <div key={warning.id} className="warning-banner">
            <AlertCircle size={16} />
            <span>{warning.text}</span>
          </div>
        ))}

        <div className="summary-card">
          <h3>Итоговые настройки</h3>
          <div className="summary-row">
            <span>Имя бота:</span>
            <strong>{formData.botName || 'Не указано'}</strong>
          </div>
          <div className="summary-row">
            <span>Режим:</span>
            <strong>{formData.dryRun ? '🧪 Dry Run' : '🔴 Боевой'}</strong>
          </div>
          <div className="summary-row">
            <span>API-ключ:</span>
            <strong>
              {formData.dryRun
                ? '— (Dry Run)'
                : selectedKey
                  ? `${selectedKey.name} (${selectedKey.exchange.toUpperCase()})`
                  : '—'}
            </strong>
          </div>
          <div className="summary-row">
            <span>Депозит бота:</span>
            <strong>{formData.stakeAmount} USDT</strong>
          </div>
          <div className="summary-row">
            <span>Размер сделки:</span>
            <strong>
              {formData.balanceRatio}% (
              {(
                (Number(formData.stakeAmount) * Number(formData.balanceRatio)) /
                100
              ).toFixed(2)}{' '}
              USDT)
            </strong>
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
            <strong>
              {formData.algorithm === 'long' ? '📈 Лонг' : '📉 Шорт'}
            </strong>
          </div>
          <div className="summary-row">
            <span>Стратегия:</span>
            <strong>
              {formData.strategyPreset === 'custom'
                ? 'Своя'
                : (presets[formData.strategyPreset]?.name ??
                  formData.strategyPreset)}
            </strong>
          </div>
          <div className="summary-row">
            <span>Take Profit (движение цены):</span>
            <strong className="profit-text">{formData.takeProfit}%</strong>
          </div>
          {formData.useStopLoss && (
            <div className="summary-row">
              <span>Stop Loss (движение цены):</span>
              <strong className="loss-text">{formData.stopLoss}%</strong>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div
      className={`create-bot-page ${assistantEnabled && assistantOpen ? 'assistant-open' : ''}`}
    >
      <div className="create-bot-scroll">
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
                  disabled={submitting || liveBotBlocked}
                  title={
                    liveBotBlocked
                      ? `Пополните баланс до ${MIN_SERVICE_BALANCE_RUB} ₽, чтобы создать боевого бота`
                      : undefined
                  }
                >
                  <Bot size={20} />
                  {submitting ? 'Создаём бота...' : 'Создать бота'}
                </button>
              )}
            </div>
          </div>
        </div>

        <SiteFooter />
      </div>

      {assistantEnabled && (
        <>
          <AssistantLauncher
            open={assistantOpen}
            onOpen={() => setAssistantOpen(true)}
          />
          <AssistantPanel
            open={assistantOpen}
            onClose={() => setAssistantOpen(false)}
            step={currentStep}
            getSnapshot={getAssistantSnapshot}
            onApplySuggestions={handleApplySuggestions}
          />
        </>
      )}
    </div>
  );
};

export default CreateBotPage;
