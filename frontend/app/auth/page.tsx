'use client';
import React, { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Bot, Eye, EyeOff, ArrowLeft, AlertCircle, Loader } from 'lucide-react';
import Link from 'next/link';
import { CROSS_BORDER_TRANSFER } from '@/lib/legal';
import { SiteFooter } from '@/app/components/SiteFooter';
import './auth.css';

type Mode = 'login' | 'register';

const AuthContent = () => {
  const router = useRouter();
  const searchParams = useSearchParams();
  // mode всегда читаем из URL — единственный источник правды,
  // чтобы не держать его в синхронизируемом с эффектом стейте
  const mode: Mode =
    searchParams.get('mode') === 'register' ? 'register' : 'login';
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });

  // Юридические согласия. Ни одна галочка не отмечена по умолчанию —
  // предзаполненное согласие согласием не считается. crossBorder показывается
  // и требуется, только пока база лежит вне РФ (lib/legal.ts).
  // Дублируется проверкой на бэкенде: в браузере форму можно обойти.
  const [consents, setConsents] = useState({
    terms: false,
    pdn: false,
    crossBorder: false,
    marketing: false,
  });

  const emptyConsents = {
    terms: false,
    pdn: false,
    crossBorder: false,
    marketing: false,
  };

  const switchMode = (m: Mode) => {
    setError('');
    setForm({ username: '', email: '', password: '', confirmPassword: '' });
    setConsents(emptyConsents);
    router.replace(`/auth?mode=${m}`, { scroll: false });
  };

  const toggleConsent = (key: keyof typeof consents) =>
    setConsents((prev) => ({ ...prev, [key]: !prev[key] }));

  // Обязательные согласия: рассылки в их число не входят.
  const requiredConsentsGiven =
    consents.terms &&
    consents.pdn &&
    (!CROSS_BORDER_TRANSFER || consents.crossBorder);

  const validate = () => {
    if (mode === 'register') {
      if (!form.username.trim()) return 'Введите имя пользователя';
      if (form.username.length < 3)
        return 'Имя должно быть не менее 3 символов';
      if (!/\S+@\S+\.\S+/.test(form.email)) return 'Введите корректный email';
      if (form.password.length < 8)
        return 'Пароль должен быть не менее 8 символов';
      if (form.password !== form.confirmPassword) return 'Пароли не совпадают';
      if (!requiredConsentsGiven)
        return 'Отметьте все обязательные согласия ниже';
    } else {
      if (!form.email.trim()) return 'Введите email';
      if (!form.password.trim()) return 'Введите пароль';
    }
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    try {
      const endpoint =
        mode === 'login' ? '/api/auth/login' : '/api/auth/register';
      const body =
        mode === 'login'
          ? { email: form.email, password: form.password }
          : {
              username: form.username,
              email: form.email,
              password: form.password,
              accept_terms: consents.terms,
              accept_pdn: consents.pdn,
              accept_cross_border: consents.crossBorder,
              accept_marketing: consents.marketing,
            };

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const data = await res.json();

      if (!res.ok) {
        // detail может быть строкой или массивом объектов (ошибки валидации Pydantic)
        const detail = data.detail;
        if (typeof detail === 'string') {
          setError(detail);
        } else if (Array.isArray(detail)) {
          setError(detail.map((e: { msg: string }) => e.msg).join(', '));
        } else {
          setError('Что-то пошло не так');
        }
        return;
      }

      // Сохраняем токен в localStorage
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('user_id', String(data.user_id));
      localStorage.setItem('username', data.username);

      router.push('/home');
    } catch {
      setError('Ошибка соединения. Попробуйте ещё раз.');
    } finally {
      setLoading(false);
    }
  };

  const isRegister = mode === 'register';

  return (
    <div className="auth-page">
      {/* Background */}
      <div className="auth-bg">
        <div className="auth-glow g1" />
        <div className="auth-glow g2" />
        <div className="auth-grid" />
      </div>

      {/* Back to landing */}
      <Link href="/" className="auth-back">
        <ArrowLeft size={16} />
        На главную
      </Link>

      <div className="auth-inner">
        <div className="auth-card">
          {/* Logo */}
          <div className="auth-logo">
            <div className="auth-logo-icon">
              <Bot size={24} />
            </div>
            <span>CryptoBot</span>
          </div>

          {/* Title */}
          <div className="auth-header">
            <h1>{isRegister ? 'Создайте аккаунт' : 'Добро пожаловать'}</h1>
            <p>
              {isRegister
                ? 'Начните торговать автоматически уже сегодня'
                : 'Войдите, чтобы управлять ботами'}
            </p>
          </div>

          {/* Tab switcher */}
          <div className="auth-tabs">
            <button
              className={`auth-tab ${mode === 'login' ? 'active' : ''}`}
              onClick={() => switchMode('login')}
              type="button"
            >
              Вход
            </button>
            <button
              className={`auth-tab ${mode === 'register' ? 'active' : ''}`}
              onClick={() => switchMode('register')}
              type="button"
            >
              Регистрация
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="auth-form" noValidate>
            {isRegister && (
              <div className="auth-field">
                <label>Имя пользователя</label>
                <input
                  type="text"
                  placeholder="your_username"
                  value={form.username}
                  onChange={(e) =>
                    setForm({ ...form, username: e.target.value })
                  }
                  className="auth-input"
                  autoComplete="username"
                />
              </div>
            )}

            <div className="auth-field">
              <label>Email</label>
              <input
                type="email"
                placeholder="you@example.com"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="auth-input"
                autoComplete="email"
              />
            </div>

            <div className="auth-field">
              <label>Пароль</label>
              <div className="auth-pass-wrap">
                <input
                  type={showPass ? 'text' : 'password'}
                  placeholder={
                    isRegister ? 'Минимум 8 символов' : 'Введите пароль'
                  }
                  value={form.password}
                  onChange={(e) =>
                    setForm({ ...form, password: e.target.value })
                  }
                  className="auth-input"
                  autoComplete={
                    isRegister ? 'new-password' : 'current-password'
                  }
                />
                <button
                  type="button"
                  className="auth-eye"
                  onClick={() => setShowPass((v) => !v)}
                  tabIndex={-1}
                >
                  {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {isRegister && (
              <div className="auth-field">
                <label>Повторите пароль</label>
                <div className="auth-pass-wrap">
                  <input
                    type={showPass ? 'text' : 'password'}
                    placeholder="Повторите пароль"
                    value={form.confirmPassword}
                    onChange={(e) =>
                      setForm({ ...form, confirmPassword: e.target.value })
                    }
                    className="auth-input"
                    autoComplete="new-password"
                  />
                </div>
              </div>
            )}

            {isRegister && (
              <div className="auth-consents">
                <label className="auth-consent">
                  <input
                    type="checkbox"
                    checked={consents.terms}
                    onChange={() => toggleConsent('terms')}
                  />
                  <span>
                    Я принимаю{' '}
                    <Link
                      href="/legal/terms"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Пользовательское соглашение
                    </Link>
                  </span>
                </label>

                <label className="auth-consent">
                  <input
                    type="checkbox"
                    checked={consents.pdn}
                    onChange={() => toggleConsent('pdn')}
                  />
                  <span>
                    Я даю согласие на обработку персональных данных в
                    соответствии с{' '}
                    <Link
                      href="/legal/pdn-consent"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Согласием на обработку персональных данных
                    </Link>
                    . Подробности обработки — в{' '}
                    <Link
                      href="/legal/privacy-policy"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Политике обработки персональных данных
                    </Link>
                    .
                  </span>
                </label>

                {CROSS_BORDER_TRANSFER && (
                  <label className="auth-consent">
                    <input
                      type="checkbox"
                      checked={consents.crossBorder}
                      onChange={() => toggleConsent('crossBorder')}
                    />
                    <span>
                      Я согласен на{' '}
                      <Link
                        href="/legal/pdn-consent#cross-border"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        трансграничную передачу моих персональных данных
                      </Link>{' '}
                      — серверы сервиса расположены за пределами РФ
                    </span>
                  </label>
                )}

                <label className="auth-consent optional">
                  <input
                    type="checkbox"
                    checked={consents.marketing}
                    onChange={() => toggleConsent('marketing')}
                  />
                  <span>
                    Хочу получать письма и push-уведомления с новостями сервиса
                    и предложениями <em>(необязательно)</em>
                  </span>
                </label>
              </div>
            )}

            {error && (
              <div className="auth-error">
                <AlertCircle size={15} />
                {error}
              </div>
            )}

            <button
              type="submit"
              className="auth-submit"
              disabled={loading || (isRegister && !requiredConsentsGiven)}
            >
              {loading ? (
                <>
                  <Loader size={16} className="spin" />
                  {isRegister ? 'Создание аккаунта...' : 'Вход...'}
                </>
              ) : isRegister ? (
                'Создать аккаунт'
              ) : (
                'Войти'
              )}
            </button>
          </form>

          {/* Switch hint */}
          <p className="auth-switch">
            {isRegister ? 'Уже есть аккаунт? ' : 'Нет аккаунта? '}
            <button
              type="button"
              className="auth-switch-btn"
              onClick={() => switchMode(isRegister ? 'login' : 'register')}
            >
              {isRegister ? 'Войти' : 'Зарегистрироваться'}
            </button>
          </p>
        </div>

        <SiteFooter />
      </div>
    </div>
  );
};

const AuthPage = () => {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <AuthContent />
    </Suspense>
  );
};

export default AuthPage;
