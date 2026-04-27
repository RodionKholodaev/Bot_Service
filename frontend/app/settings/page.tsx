"use client"
import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowLeft, Key, Plus, Trash2, Eye, EyeOff,
  AlertCircle, Check, Loader2, ShieldCheck, X
} from 'lucide-react';
import { apiFetch, ApiError } from '@/lib/api';
import './api-keys.css';

interface ApiKey {
  id: number;
  name: string;
  exchange: string;
  is_active: boolean;
  created_at: string;
}

interface AddKeyForm {
  name: string;
  exchange: string;
  api_key: string;
  api_secret: string;
}

const EXCHANGES = [
  { value: 'binance', label: 'Binance' },
  { value: 'bybit', label: 'Bybit' },
  { value: 'okx', label: 'OKX' },
];

const EXCHANGE_COLORS: Record<string, string> = {
  binance: '#f0b90b',
  bybit: '#f7a600',
  okx: '#00d4aa',
};

export default function ApiKeysPage() {
  const router = useRouter();

  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<AddKeyForm>({
    name: '', exchange: 'binance', api_key: '', api_secret: '',
  });
  const [showSecret, setShowSecret] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedId, setSavedId] = useState<number | null>(null);

  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);

  const loadKeys = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await apiFetch<ApiKey[]>('/api/api-keys');
      setKeys(data);
    } catch {
      setLoadError('Не удалось загрузить ключи');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadKeys(); }, []);

  const handleAdd = async () => {
    if (!form.name.trim()) { setSaveError('Укажите название'); return; }
    if (!form.api_key.trim()) { setSaveError('Введите API Key'); return; }
    if (!form.api_secret.trim()) { setSaveError('Введите API Secret'); return; }

    setSaving(true);
    setSaveError(null);
    try {
      const created = await apiFetch<ApiKey>('/api/api-keys', {
        method: 'POST',
        body: form,
      });
      setKeys(prev => [created, ...prev]);
      setSavedId(created.id);
      setForm({ name: '', exchange: 'binance', api_key: '', api_secret: '' });
      setShowForm(false);
      setTimeout(() => setSavedId(null), 3000);
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : 'Ошибка при сохранении');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    setDeletingId(id);
    try {
      await apiFetch(`/api/api-keys/${id}`, { method: 'DELETE' });
      setKeys(prev => prev.filter(k => k.id !== id));
    } catch {
      // можно показать toast
    } finally {
      setDeletingId(null);
      setConfirmDeleteId(null);
    }
  };

  const formatDate = (iso: string) => {
    return new Date(iso).toLocaleDateString('ru-RU', {
      day: '2-digit', month: 'short', year: 'numeric',
    });
  };

  return (
    <div className="ak-page">
      {/* Фоновые декорации */}
      <div className="ak-bg-glow ak-bg-glow--1" />
      <div className="ak-bg-glow ak-bg-glow--2" />

      {/* Шапка */}
      <div className="ak-header">
        <button className="ak-back-btn" onClick={() => router.back()}>
          <ArrowLeft size={18} />
          Назад
        </button>
        <div className="ak-header-title">
          <ShieldCheck size={26} className="ak-header-icon" />
          <div>
            <h1>API-ключи</h1>
            <p>Управляйте подключениями к биржам</p>
          </div>
        </div>
        <button
          className="ak-add-btn"
          onClick={() => { setShowForm(true); setSaveError(null); }}
        >
          <Plus size={18} />
          Добавить ключ
        </button>
      </div>

      <div className="ak-content">

        {/* Форма добавления */}
        {showForm && (
          <div className="ak-form-card">
            <div className="ak-form-card__header">
              <div className="ak-form-card__title">
                <Key size={20} />
                Новый API-ключ
              </div>
              <button className="ak-form-close" onClick={() => setShowForm(false)}>
                <X size={18} />
              </button>
            </div>

            <div className="ak-form-body">
              <div className="ak-form-row">
                <div className="ak-field">
                  <label>Название</label>
                  <input
                    type="text"
                    placeholder="Например: Мой Binance"
                    value={form.name}
                    onChange={e => setForm({ ...form, name: e.target.value })}
                    className="ak-input"
                    maxLength={100}
                  />
                </div>
                <div className="ak-field ak-field--sm">
                  <label>Биржа</label>
                  <select
                    value={form.exchange}
                    onChange={e => setForm({ ...form, exchange: e.target.value })}
                    className="ak-select"
                  >
                    {EXCHANGES.map(ex => (
                      <option key={ex.value} value={ex.value}>{ex.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="ak-field">
                <label>API Key</label>
                <input
                  type="text"
                  placeholder="Вставьте API Key"
                  value={form.api_key}
                  onChange={e => setForm({ ...form, api_key: e.target.value })}
                  className="ak-input ak-input--mono"
                  autoComplete="off"
                />
              </div>

              <div className="ak-field">
                <label>API Secret</label>
                <div className="ak-input-wrap">
                  <input
                    type={showSecret ? 'text' : 'password'}
                    placeholder="Вставьте API Secret"
                    value={form.api_secret}
                    onChange={e => setForm({ ...form, api_secret: e.target.value })}
                    className="ak-input ak-input--mono ak-input--padded"
                    autoComplete="off"
                  />
                  <button
                    className="ak-eye-btn"
                    onClick={() => setShowSecret(v => !v)}
                    type="button"
                  >
                    {showSecret ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              <div className="ak-notice">
                <ShieldCheck size={15} />
                Ключ шифруется перед сохранением. Secret не отображается после добавления.
              </div>

              {saveError && (
                <div className="ak-error">
                  <AlertCircle size={15} />
                  {saveError}
                </div>
              )}

              <div className="ak-form-actions">
                <button
                  className="ak-cancel-btn"
                  onClick={() => setShowForm(false)}
                  disabled={saving}
                >
                  Отмена
                </button>
                <button
                  className="ak-save-btn"
                  onClick={handleAdd}
                  disabled={saving}
                >
                  {saving
                    ? <><Loader2 size={16} className="spin" /> Сохраняем...</>
                    : <><Check size={16} /> Сохранить</>
                  }
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Список ключей */}
        <div className="ak-list-section">
          <div className="ak-list-header">
            <span>Сохранённые ключи</span>
            {!loading && <span className="ak-count">{keys.length}</span>}
          </div>

          {loading && (
            <div className="ak-state-placeholder">
              <Loader2 size={28} className="spin ak-state-icon" />
              <p>Загружаем ключи...</p>
            </div>
          )}

          {!loading && loadError && (
            <div className="ak-state-placeholder ak-state-placeholder--error">
              <AlertCircle size={28} className="ak-state-icon" />
              <p>{loadError}</p>
              <button className="ak-retry-btn" onClick={loadKeys}>Повторить</button>
            </div>
          )}

          {!loading && !loadError && keys.length === 0 && (
            <div className="ak-state-placeholder">
              <Key size={36} className="ak-state-icon ak-state-icon--muted" />
              <p>Ключей пока нет</p>
              <span>Добавьте первый API-ключ, чтобы запустить бота</span>
            </div>
          )}

          {!loading && !loadError && keys.length > 0 && (
            <div className="ak-list">
              {keys.map(key => (
                <div
                  key={key.id}
                  className={`ak-key-card ${savedId === key.id ? 'ak-key-card--new' : ''}`}
                >
                  <div
                    className="ak-key-exchange-bar"
                    style={{ background: EXCHANGE_COLORS[key.exchange] ?? '#3b82f6' }}
                  />
                  <div className="ak-key-body">
                    <div className="ak-key-info">
                      <div className="ak-key-name">
                        {key.name}
                        {savedId === key.id && (
                          <span className="ak-new-badge">
                            <Check size={11} /> Добавлен
                          </span>
                        )}
                      </div>
                      <div className="ak-key-meta">
                        <span
                          className="ak-exchange-badge"
                          style={{ color: EXCHANGE_COLORS[key.exchange] ?? '#3b82f6' }}
                        >
                          {key.exchange.toUpperCase()}
                        </span>
                        <span className="ak-key-date">с {formatDate(key.created_at)}</span>
                      </div>
                    </div>

                    <div className="ak-key-actions">
                      {confirmDeleteId === key.id ? (
                        <div className="ak-confirm-row">
                          <span>Удалить?</span>
                          <button
                            className="ak-confirm-yes"
                            onClick={() => handleDelete(key.id)}
                            disabled={deletingId === key.id}
                          >
                            {deletingId === key.id
                              ? <Loader2 size={14} className="spin" />
                              : 'Да'
                            }
                          </button>
                          <button
                            className="ak-confirm-no"
                            onClick={() => setConfirmDeleteId(null)}
                          >
                            Нет
                          </button>
                        </div>
                      ) : (
                        <button
                          className="ak-delete-btn"
                          onClick={() => setConfirmDeleteId(key.id)}
                          title="Удалить ключ"
                        >
                          <Trash2 size={16} />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}