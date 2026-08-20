/* Карта «slug → компонент статьи».
 *
 * Ключи обязаны совпадать со slug'ами из meta.ts — рассинхрон любой из сторон
 * страница статьи трактует как 404 (см. [slug]/page.tsx), так что забытая
 * запись обнаружится сразу, а не отрендерит пустую страницу.
 *
 * Все статьи — серверные компоненты, поэтому импорт их всех разом ничего не
 * стоит браузеру: в бандл клиента отсюда не уезжает ничего. */

import React from 'react';

import { KakEtoRabotaet } from './articles/kak-eto-rabotaet';
import { ApiKlyuchBybit } from './articles/api-klyuch-bybit';
import { PervyjBot } from './articles/pervyj-bot';
import { Strategii } from './articles/strategii';
import { TakeProfitIStopLoss } from './articles/take-profit-i-stop-loss';
import { DemoIRealnyeTorgi } from './articles/demo-i-realnye-torgi';
import { UpravlenieBotom } from './articles/upravlenie-botom';
import { KakChitatStatistiku } from './articles/kak-chitat-statistiku';
import { KomissiyaIBalans } from './articles/komissiya-i-balans';
import { ChastyeVoprosy } from './articles/chastye-voprosy';

export const CONTENT: Record<string, React.ComponentType> = {
  'kak-eto-rabotaet': KakEtoRabotaet,
  'api-klyuch-bybit': ApiKlyuchBybit,
  'pervyj-bot': PervyjBot,
  strategii: Strategii,
  'take-profit-i-stop-loss': TakeProfitIStopLoss,
  'demo-i-realnye-torgi': DemoIRealnyeTorgi,
  'upravlenie-botom': UpravlenieBotom,
  'kak-chitat-statistiku': KakChitatStatistiku,
  'komissiya-i-balans': KomissiyaIBalans,
  'chastye-voprosy': ChastyeVoprosy,
};
