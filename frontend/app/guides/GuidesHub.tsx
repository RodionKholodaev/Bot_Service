'use client';

/* Хаб раздела «Обучение»: поиск + карточки статей по категориям.
 *
 * Клиентский он только ради поиска. Сам поиск — по заголовку, описанию и
 * ключевым словам из meta.ts, без индекса и без запроса на бэкенд: статей
 * десяток, фильтровать их в памяти дешевле, чем городить эндпоинт. */

import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import {
  Search,
  ArrowRight,
  Clock,
  SearchX,
  MessageCircle,
  Sparkles,
} from 'lucide-react';
import { CATEGORIES, GUIDES, type GuideMeta } from './meta';

// Быстрый старт — маршрут «с нуля до запущенного бота» четырьмя ссылками.
// Ведёт на те же статьи, просто в правильном порядке.
const QUICK_START = [
  { slug: 'kak-eto-rabotaet', label: 'Понять, как всё устроено' },
  { slug: 'api-klyuch-bybit', label: 'Подключить ключ Bybit' },
  { slug: 'pervyj-bot', label: 'Создать первого бота' },
  { slug: 'demo-i-realnye-torgi', label: 'Перейти на реальные торги' },
];

const matches = (g: GuideMeta, query: string): boolean => {
  const haystack = [g.title, g.description, ...g.keywords]
    .join(' ')
    .toLowerCase();
  // Все слова запроса должны найтись: «стоп лосс» не должен выдавать всё
  // подряд из-за того, что слово «стоп» встречается в одной статье.
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => haystack.includes(word));
};

const GuideCard = ({ guide }: { guide: GuideMeta }) => (
  <Link href={`/guides/${guide.slug}`} className="gd-card">
    <div className="gd-card-top">
      <h3>{guide.title}</h3>
      <ArrowRight size={18} className="gd-card-arrow" />
    </div>
    <p>{guide.description}</p>
    <div className="gd-card-meta">
      <Clock size={13} />
      <span>{guide.readMinutes} мин чтения</span>
    </div>
  </Link>
);

export const GuidesHub = () => {
  const [query, setQuery] = useState('');

  const found = useMemo(() => {
    const q = query.trim();
    return q ? GUIDES.filter((g) => matches(g, q)) : GUIDES;
  }, [query]);

  const isSearching = query.trim().length > 0;

  return (
    <main className="gd-main">
      {/* ===== HERO + ПОИСК ===== */}
      <section className="gd-hero">
        <h1>Обучение</h1>
        <p className="gd-hero-sub">
          Всё, что нужно знать, чтобы запустить своего первого торгового бота —
          без опыта в трейдинге и без единой строчки кода. Читайте по порядку
          или найдите конкретный ответ поиском.
        </p>
        <div className="gd-search-wrap">
          <span className="gd-search-icon">
            <Search size={18} />
          </span>
          <input
            className="gd-search"
            type="text"
            placeholder="Поиск по гайдам: плечо, комиссия, стоп-лосс..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Поиск по гайдам"
          />
        </div>
      </section>

      {/* ===== БЫСТРЫЙ СТАРТ (прячем во время поиска) ===== */}
      {!isSearching && (
        <section className="gd-quickstart">
          <div className="gd-quickstart-title">
            <Sparkles size={19} />
            Быстрый старт
          </div>
          <p className="gd-quickstart-sub">
            Четыре шага от «первый раз вижу этот сайт» до работающего бота.
          </p>
          <div className="gd-quickstart-steps">
            {QUICK_START.map((s, i) => (
              <Link
                key={s.slug}
                href={`/guides/${s.slug}`}
                className="gd-qs-step"
              >
                <span className="gd-qs-num">{i + 1}</span>
                <span>{s.label}</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* ===== РЕЗУЛЬТАТЫ ПОИСКА ===== */}
      {isSearching ? (
        found.length > 0 ? (
          <section className="gd-category">
            <div className="gd-category-head">
              <div className="gd-category-icon">
                <Search size={19} />
              </div>
              <div>
                <h2>Найдено: {found.length}</h2>
                <p>По запросу «{query.trim()}»</p>
              </div>
            </div>
            <div className="gd-cards">
              {found.map((g) => (
                <GuideCard key={g.slug} guide={g} />
              ))}
            </div>
          </section>
        ) : (
          <div className="gd-empty">
            <div className="gd-empty-icon">
              <SearchX size={40} />
            </div>
            <h3>Ничего не нашлось</h3>
            <p>
              Попробуйте другое слово — или напишите нам в поддержку, и мы
              ответим лично.
            </p>
          </div>
        )
      ) : (
        /* ===== ОБЫЧНЫЙ ВИД: КАТЕГОРИИ ===== */
        CATEGORIES.map((cat) => {
          const items = GUIDES.filter((g) => g.category === cat.id);
          if (items.length === 0) return null;
          return (
            <section key={cat.id} className="gd-category">
              <div className="gd-category-head">
                <div className="gd-category-icon">
                  <cat.Icon size={19} />
                </div>
                <div>
                  <h2>{cat.title}</h2>
                  <p>{cat.subtitle}</p>
                </div>
              </div>
              <div className="gd-cards">
                {items.map((g) => (
                  <GuideCard key={g.slug} guide={g} />
                ))}
              </div>
            </section>
          );
        })
      )}

      {/* ===== НЕ НАШЛИ ОТВЕТ ===== */}
      <section className="gd-help">
        <div>
          <h3>Не нашли ответ?</h3>
          <p>
            Опишите вопрос — обычно отвечаем в течение 2–4 часов в рабочее
            время.
          </p>
        </div>
        <div className="gd-help-actions">
          <Link href="/feedback" className="gd-btn-primary">
            <MessageCircle size={17} />
            Написать в поддержку
          </Link>
        </div>
      </section>
    </main>
  );
};
