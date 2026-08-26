/* Общий футер сайта: ссылки на юридические документы + дисклеймер о рисках.
 *
 * Требование 152-ФЗ — документы должны открываться в один клик с любой
 * страницы, поэтому этот блок вставлен в конец скролл-контейнера каждой
 * страницы (/home, /stats, /settings, /bot-creation, /feedback, /guides,
 * /auth, /legal/*), а не в корневой layout: страницы сделаны как
 * `height: 100vh; overflow: hidden` со своим внутренним скроллом, и футер из
 * layout оказался бы за пределами видимой области.
 *
 * На лендинге (app/page.tsx) свой оформленный футер — там ссылки добавлены
 * прямо в него, чтобы не рисовать две одинаковые полосы подряд. */

import Link from 'next/link';
import { LEGAL_LINKS } from '@/lib/legal';
import './site-footer.css';

export const SiteFooter = () => (
  <footer className="site-footer">
    <nav className="site-footer-links">
      {LEGAL_LINKS.map((link) => (
        <Link key={link.href} href={link.href} className="site-footer-link">
          {link.title}
        </Link>
      ))}
    </nav>
    <p className="site-footer-note">
      Торговля криптовалютой с использованием кредитного плеча связана с риском
      убытков. Сервис не является инвестиционной рекомендацией и не гарантирует
      доход. 18+
    </p>
  </footer>
);

export default SiteFooter;
