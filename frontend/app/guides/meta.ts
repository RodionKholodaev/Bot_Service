/* Реестр статей раздела «Обучение» — только метаданные, без самого текста.
 *
 * Отделено от content.tsx намеренно: хаб /guides — клиентский компонент
 * (там живой поиск), и если бы список статей тянул за собой их содержимое,
 * весь текст раздела уехал бы в браузерный бандл хаба. Здесь — чистые данные.
 *
 * Порядок в GUIDES задаёт две вещи сразу: порядок карточек внутри категории
 * и переходы «Назад / Далее» внизу статьи. Это осознанно один список, а не
 * два: расходясь, они дают читателю «Далее» на статью, которую он уже прочёл. */

import {
  Rocket,
  Bot,
  LineChart,
  Wallet,
  HelpCircle,
  type LucideIcon,
} from 'lucide-react';

export type CategoryId = 'start' | 'create' | 'manage' | 'money' | 'faq';

export interface Category {
  id: CategoryId;
  title: string;
  subtitle: string;
  Icon: LucideIcon;
}

export const CATEGORIES: Category[] = [
  {
    id: 'start',
    title: 'Начало работы',
    subtitle: 'С чего начать, если вы здесь впервые',
    Icon: Rocket,
  },
  {
    id: 'create',
    title: 'Создание бота',
    subtitle: 'Настройки, стратегии и выход из сделки',
    Icon: Bot,
  },
  {
    id: 'manage',
    title: 'Управление и мониторинг',
    subtitle: 'Как следить за ботами и читать результаты',
    Icon: LineChart,
  },
  {
    id: 'money',
    title: 'Деньги',
    subtitle: 'Комиссия сервиса и пополнение баланса',
    Icon: Wallet,
  },
  {
    id: 'faq',
    title: 'Вопросы и ответы',
    subtitle: 'Короткие ответы на частые вопросы',
    Icon: HelpCircle,
  },
];

export interface GuideMeta {
  slug: string;
  title: string;
  /** Показывается на карточке в хабе и уходит в <meta name="description"> */
  description: string;
  category: CategoryId;
  readMinutes: number;
  /** Дополнительные слова для поиска по хабу — то, что читатель наберёт,
   *  но чего может не быть в заголовке («ключ», «плечо», «убыток»). */
  keywords: string[];
}

export const GUIDES: GuideMeta[] = [
  {
    slug: 'kak-eto-rabotaet',
    title: 'Что такое CryptoBot и как он работает',
    description:
      'За 5 минут: что делает торговый бот, где лежат ваши деньги и почему первый запуск ничем не рискует.',
    category: 'start',
    readMinutes: 5,
    keywords: [
      'начало',
      'основы',
      'что это',
      'принцип работы',
      'новичок',
      'freqtrade',
    ],
  },
  {
    slug: 'api-klyuch-bybit',
    title: 'Как подключить API-ключ Bybit',
    description:
      'Пошагово создаём ключ на бирже и выдаём ему только те права, которые нужны для торговли — без права вывода средств.',
    category: 'start',
    readMinutes: 7,
    keywords: [
      'ключ',
      'api',
      'bybit',
      'биржа',
      'безопасность',
      'права',
      'подключить',
    ],
  },
  {
    slug: 'pervyj-bot',
    title: 'Создаём первого бота: пошагово',
    description:
      'Разбираем все четыре шага мастера создания — от депозита и торговой пары до имени бота и режима запуска.',
    category: 'create',
    readMinutes: 9,
    keywords: [
      'создать',
      'первый бот',
      'мастер',
      'депозит',
      'пара',
      'плечо',
      'настройка',
    ],
  },
  {
    slug: 'strategii',
    title: 'Стратегии: готовые пресеты и ручная настройка',
    description:
      'Чем отличаются консервативная, умеренная и агрессивная стратегии, что такое RSI и CCI и когда стоит собирать условия вручную.',
    category: 'create',
    readMinutes: 10,
    keywords: [
      'стратегия',
      'rsi',
      'cci',
      'индикаторы',
      'пресет',
      'консервативная',
      'агрессивная',
      'фильтры',
    ],
  },
  {
    slug: 'take-profit-i-stop-loss',
    title: 'Тейк-профит и стоп-лосс простыми словами',
    description:
      'Два числа, которые решают, когда бот закроет сделку. Как их выбрать и почему плечо меняет их смысл.',
    category: 'create',
    readMinutes: 7,
    keywords: [
      'тейк профит',
      'стоп лосс',
      'tp',
      'sl',
      'убыток',
      'прибыль',
      'выход из сделки',
      'ликвидация',
    ],
  },
  {
    slug: 'demo-i-realnye-torgi',
    title: 'Демо-режим и реальная торговля',
    description:
      'Чем отличается симуляция от боевого режима, сколько тестировать бота и как перейти на реальные деньги.',
    category: 'create',
    readMinutes: 6,
    keywords: [
      'демо',
      'dry run',
      'симуляция',
      'боевой режим',
      'реальные деньги',
      'тест',
    ],
  },
  {
    slug: 'upravlenie-botom',
    title: 'Запуск, остановка и удаление бота',
    description:
      'Что означает каждый статус бота, что происходит с открытой сделкой при остановке и что теряется при удалении.',
    category: 'manage',
    readMinutes: 6,
    keywords: [
      'запустить',
      'остановить',
      'удалить',
      'статус',
      'ошибка',
      'логи',
      'управление',
    ],
  },
  {
    slug: 'kak-chitat-statistiku',
    title: 'Как читать статистику',
    description:
      'График прибыли, винрейт и максимальная просадка: что именно считает каждая цифра и на какие из них смотреть.',
    category: 'manage',
    readMinutes: 8,
    keywords: [
      'статистика',
      'график',
      'винрейт',
      'просадка',
      'pnl',
      'прибыль',
      'сделки',
      'отчёт',
    ],
  },
  {
    slug: 'komissiya-i-balans',
    title: 'Комиссия сервиса и пополнение баланса',
    description:
      'Сервис берёт 10% только с прибыльных сделок и списывает их в рублях. Разбираем на числах и пополняем баланс.',
    category: 'money',
    readMinutes: 6,
    keywords: [
      'комиссия',
      'баланс',
      'оплата',
      'пополнить',
      'деньги',
      'рубли',
      'тариф',
      'списание',
    ],
  },
  {
    slug: 'chastye-voprosy',
    title: 'Частые вопросы',
    description:
      'Бот не запускается, сделок нет, цифры не сходятся — короткие ответы на то, с чем сталкиваются чаще всего.',
    category: 'faq',
    readMinutes: 8,
    keywords: [
      'проблема',
      'не работает',
      'ошибка',
      'вопрос',
      'помощь',
      'нет сделок',
      'faq',
    ],
  },
];

export const getGuide = (slug: string): GuideMeta | undefined =>
  GUIDES.find((g) => g.slug === slug);

/** Соседи по списку — для блока «Назад / Далее» внизу статьи. */
export const getNeighbours = (slug: string) => {
  const i = GUIDES.findIndex((g) => g.slug === slug);
  return {
    prev: i > 0 ? GUIDES[i - 1] : null,
    next: i >= 0 && i < GUIDES.length - 1 ? GUIDES[i + 1] : null,
  };
};
