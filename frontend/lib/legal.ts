// Юридические документы сервиса: реквизиты, редакции и адреса страниц.
//
// ЕДИНСТВЕННОЕ место, где нужно заполнить данные оператора: все три документа
// (/legal/terms, /legal/privacy-policy, /legal/pdn-consent) и футер берут их
// отсюда. Пока в значениях стоит [ЗАПОЛНИТЬ: ...], этот текст так и печатается
// на странице — специально, чтобы незаполненное было видно сразу.
//
// Редакции продублированы на бэкенде (backend/src/core/legal.py) — именно
// оттуда версия попадает в consent_log при регистрации. Меняешь текст
// документа — поднимаешь дату В ОБОИХ местах, иначе в логе согласий будет
// стоять версия, которой человек не видел.

export const SERVICE_NAME = 'Rudder';
export const SERVICE_DOMAIN = 'rudder-trade.ru';
export const SERVICE_URL = 'https://rudder-trade.ru';

/** Реквизиты оператора — самозанятого (НПД). */
export const OPERATOR = {
  fullName: 'Холодаев Родион Сергеевич',
  status:
    'самозанятый (плательщик налога на профессиональный доход, ФЗ № 422-ФЗ от 27.11.2018)',
  inn: '511590068032',
  address: 'г. Москва ул. Москворечье 2 к. 2',
  /** Email для обращений по вопросам персональных данных и отзыва согласия. */
  pdnEmail: 'kholodaev10@gmail.com',
  /** Email для вопросов по услугам и претензий. */
  supportEmail: 'kholodaev10@gmail.com',
};

/** Где физически находятся серверы с базой данных. */
export const DATA_LOCATION = 'Германия';

// База данных физически расположена вне РФ, поэтому трансграничная передача
// есть и на неё требуется ОТДЕЛЬНОЕ согласие (152-ФЗ, ст. 12) — отдельным
// чекбоксом на форме регистрации, а не тем же, что общее согласие.
// Если база переедет в РФ — false здесь И в backend/src/core/legal.py.
export const CROSS_BORDER_TRANSFER = true;

/** Вознаграждение сервиса — доля прибыли закрытой сделки (backend: SERVICE_COMMISION). */
export const SERVICE_COMMISSION_PERCENT = 10;

/** Плата за каждого бота сверх бесплатных: одного демо и одного боевого. */
export const EXTRA_BOT_PRICE_RUB = 200;

/** Даты редакций документов. Формат ISO, на страницах печатаются как дд.мм.гггг. */
export const LEGAL_VERSIONS = {
  terms: '2026-08-26',
  privacyPolicy: '2026-08-26',
  pdnConsent: '2026-08-26',
} as const;

/** Ссылки для футера и шапки юридических страниц. Порядок общий для всего сайта. */
export const LEGAL_LINKS = [
  { href: '/legal/terms', title: 'Пользовательское соглашение' },
  {
    href: '/legal/privacy-policy',
    title: 'Политика обработки персональных данных',
  },
  {
    href: '/legal/pdn-consent',
    title: 'Согласие на обработку персональных данных',
  },
] as const;

/** '2026-08-26' -> '26.08.2026'. */
export const formatLegalVersion = (version: string): string => {
  const [year, month, day] = version.split('-');
  return `${day}.${month}.${year}`;
};
