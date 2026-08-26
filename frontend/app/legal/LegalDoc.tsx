/* Каркас юридической страницы: шапка с возвратом на сайт, текст документа,
 * общий футер.
 *
 * Серверный компонент без состояния — документы должны открываться по прямой
 * ссылке, без авторизации и без JS. По той же причине это обычный HTML-текст
 * на странице, а не PDF на скачивание. */

import React from 'react';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { SiteFooter } from '@/app/components/SiteFooter';
import {
  LEGAL_LINKS,
  SERVICE_DOMAIN,
  SERVICE_NAME,
  formatLegalVersion,
} from '@/lib/legal';
import './legal.css';

interface LegalDocProps {
  title: string;
  /** Дата редакции в формате ISO — та же, что в lib/legal.ts и в consent_log. */
  version: string;
  /** Адрес этой же страницы: в шапке она подсвечивается как активная. */
  href: string;
  children: React.ReactNode;
}

export const LegalDoc = ({ title, version, href, children }: LegalDocProps) => (
  <div className="legal-page">
    <header className="legal-topbar">
      <Link href="/" className="legal-back">
        <ArrowLeft size={16} />
        На сайт
      </Link>
      <nav className="legal-nav">
        {LEGAL_LINKS.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={`legal-nav-item ${link.href === href ? 'active' : ''}`}
          >
            {link.title}
          </Link>
        ))}
      </nav>
    </header>

    <div className="legal-scroll">
      <article className="legal-doc">
        <h1>{title}</h1>
        <p className="legal-meta">
          Сервис {SERVICE_NAME} ({SERVICE_DOMAIN}) · редакция от{' '}
          {formatLegalVersion(version)}
        </p>
        {children}
      </article>
      <SiteFooter />
    </div>
  </div>
);

export default LegalDoc;
