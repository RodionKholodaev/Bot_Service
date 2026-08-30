import type { Metadata } from 'next';
import { GuidesShell } from './GuidesShell';
import { GuidesHub } from './GuidesHub';

/* Серверная обёртка хаба. Нужна ровно ради metadata: экспортировать её из
 * клиентского компонента (а GuidesHub клиентский из-за поиска) нельзя. */

export const metadata: Metadata = {
  description:
    'Гайды по Rudder: как подключить биржу, создать торгового бота, настроить стратегию и читать статистику.',
};

export default function GuidesPage() {
  return (
    <GuidesShell>
      <GuidesHub />
    </GuidesShell>
  );
}
