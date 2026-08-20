/* Кирпичики, из которых собираются статьи.
 *
 * Все — обычные презентационные компоненты без состояния, поэтому остаются
 * серверными: статья не тащит в браузер ни строчки лишнего JS. Аккордеон FAQ
 * работает на нативном <details>, а не на useState, ровно по этой же причине. */

import React from 'react';
import { Info, Lightbulb, AlertTriangle, ShieldAlert, ChevronDown } from 'lucide-react';

// ── Выноска ────────────────────────────────────────────────
type CalloutKind = 'info' | 'tip' | 'warning' | 'danger';

const CALLOUT_ICON: Record<CalloutKind, React.ComponentType<{ size?: number }>> = {
  info: Info,
  tip: Lightbulb,
  warning: AlertTriangle,
  danger: ShieldAlert,
};

export const Callout = ({
  kind = 'info',
  title,
  children,
}: {
  kind?: CalloutKind;
  title?: string;
  children: React.ReactNode;
}) => {
  const Icon = CALLOUT_ICON[kind];
  return (
    <div className={`gd-callout ${kind}`}>
      <span className="gd-callout-icon">
        <Icon size={19} />
      </span>
      <div className="gd-callout-body">
        {title && <div className="gd-callout-title">{title}</div>}
        {children}
      </div>
    </div>
  );
};

// ── Пошаговая инструкция ───────────────────────────────────
export const Steps = ({ children }: { children: React.ReactNode }) => (
  <div className="gd-steps">{children}</div>
);

export const Step = ({
  n,
  title,
  children,
}: {
  n: number;
  title: string;
  children?: React.ReactNode;
}) => (
  <div className="gd-step">
    <div className="gd-step-num">{n}</div>
    <div className="gd-step-title">{title}</div>
    {children && <div className="gd-step-body">{children}</div>}
  </div>
);

// ── Таблица ────────────────────────────────────────────────
/** Обёртка обязательна: на узком экране таблица должна скроллиться сама,
 *  а не растягивать страницу по горизонтали. */
export const Table = ({
  head,
  rows,
}: {
  head: string[];
  rows: React.ReactNode[][];
}) => (
  <div className="gd-table-wrap">
    <table className="gd-table">
      <thead>
        <tr>
          {head.map((h, i) => (
            <th key={i}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i}>
            {row.map((cell, j) => (
              <td key={j}>{cell}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

// ── FAQ-аккордеон ──────────────────────────────────────────
export const Faq = ({ children }: { children: React.ReactNode }) => (
  <div className="gd-faq">{children}</div>
);

export const FaqItem = ({
  q,
  children,
}: {
  q: string;
  children: React.ReactNode;
}) => (
  <details className="gd-faq-item">
    <summary className="gd-faq-q">
      <span>{q}</span>
      <ChevronDown size={18} className="gd-faq-chevron" />
    </summary>
    <div className="gd-faq-a">{children}</div>
  </details>
);
