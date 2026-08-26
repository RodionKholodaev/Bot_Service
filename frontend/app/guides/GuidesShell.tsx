'use client';

/* Общий каркас раздела «Обучение»: шапка + скроллящаяся область.
 *
 * В отличие от /home, /stats и /feedback, гайды доступны БЕЗ авторизации —
 * человек должен успеть прочитать, как всё устроено, ещё до регистрации.
 * Поэтому здесь нет router.replace('/auth'): вместо баланса гостю
 * показывается кнопка «Войти».
 *
 * Клиентский компонент нужен ровно ради этого: токен лежит в localStorage,
 * на сервере его не видно. Сам текст статей приходит сюда пропсом children
 * из серверного компонента и остаётся серверным. */

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Zap, Settings, CreditCard, LogIn } from 'lucide-react';
import { apiFetch } from '@/lib/api';
import { SiteFooter } from '@/app/components/SiteFooter';
import './guides.css';

// тот же светофор баланса, что на главной, в статистике и в обратной связи
const getBalanceStatus = (balance: number): string => {
  if (balance < 100) return 'critical';
  if (balance < 1000) return 'low';
  return 'good';
};

export const GuidesShell = ({ children }: { children: React.ReactNode }) => {
  const [isAuthed, setIsAuthed] = useState(false);
  const [serviceBalance, setServiceBalance] = useState<number>(0);

  useEffect(() => {
    // localStorage доступен только в браузере, при серверном рендере токена
    // не видно — узнать про авторизацию раньше монтирования нельзя.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIsAuthed(Boolean(localStorage.getItem('access_token')));
  }, []);

  useEffect(() => {
    if (!isAuthed) return;
    // Баланс нужен только для индикатора в шапке. Молча игнорируем ошибку:
    // из-за неё статья не должна перестать открываться.
    apiFetch<{ service_balance: number }>('/users/me/balance')
      .then((data) => setServiceBalance(data.service_balance))
      .catch(() => {});
  }, [isAuthed]);

  return (
    <div className="gd-page">
      <header className="gd-topbar">
        <div className="gd-topbar-left">
          <Link href={isAuthed ? '/home' : '/'} className="gd-brand">
            <Zap size={28} />
            <span>CryptoBot</span>
          </Link>
          <nav className="gd-nav">
            <Link href={isAuthed ? '/home' : '/'} className="gd-nav-item">
              Главная
            </Link>
            {isAuthed && (
              <Link href="/stats" className="gd-nav-item">
                Статистика
              </Link>
            )}
            {isAuthed && (
              <Link href="/feedback" className="gd-nav-item">
                Обратная связь
              </Link>
            )}
            <Link href="/guides" className="gd-nav-item active">
              Обучение
            </Link>
          </nav>
        </div>

        <div className="gd-topbar-right">
          {isAuthed ? (
            <>
              <div className={`gd-balance ${getBalanceStatus(serviceBalance)}`}>
                <CreditCard size={16} />
                <span>{serviceBalance.toLocaleString('ru-RU')} ₽</span>
              </div>
              <Link href="/settings">
                <button className="gd-icon-btn" aria-label="Настройки">
                  <Settings size={20} />
                </button>
              </Link>
            </>
          ) : (
            <Link href="/auth" className="gd-login-btn">
              <LogIn size={16} />
              Войти
            </Link>
          )}
        </div>
      </header>

      <div className="gd-scroll">
        {children}
        <SiteFooter />
      </div>
    </div>
  );
};
