'use client';

/* Оглавление статьи.
 *
 * Пункты строятся из самого текста — компонент после монтирования ищет в
 * .gd-body все <h2 id="...">. Намеренно не держим отдельный список заголовков
 * в метаданных статьи: такой список неизбежно разъезжается с текстом, когда
 * заголовок переименовали, а мету поправить забыли.
 *
 * Активный пункт подсвечивается через IntersectionObserver. root — это
 * .gd-scroll, а не окно: страница скроллится внутри контейнера, и наблюдатель
 * с root=null просто не срабатывал бы. */

import React, { useEffect, useState } from 'react';

interface Heading {
  id: string;
  text: string;
}

export const GuideToc = () => {
  const [headings, setHeadings] = useState<Heading[]>([]);
  const [activeId, setActiveId] = useState<string>('');

  useEffect(() => {
    const nodes = Array.from(
      document.querySelectorAll<HTMLHeadingElement>('.gd-body h2[id]'),
    );
    // Заголовки берутся из уже отрисованного DOM, до первого рендера их
    // не существует — посчитать список заранее физически нельзя. Правило
    // ловит лишние каскадные перерисовки, здесь вторая отрисовка обязательна.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHeadings(nodes.map((n) => ({ id: n.id, text: n.textContent ?? '' })));

    if (nodes.length === 0) return;

    const root = document.querySelector('.gd-scroll');
    const observer = new IntersectionObserver(
      (entries) => {
        // Активным считаем самый верхний заголовок из попавших в зону
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible.length > 0) setActiveId(visible[0].target.id);
      },
      {
        root,
        // Зона — верхние 30% контейнера: заголовок становится активным,
        // когда доезжает до верха экрана, а не когда только появляется снизу.
        rootMargin: '0px 0px -70% 0px',
        threshold: 0,
      },
    );

    nodes.forEach((n) => observer.observe(n));
    return () => observer.disconnect();
  }, []);

  // До монтирования заголовков ещё нет — не рисуем пустую коробку
  if (headings.length === 0) return null;

  return (
    <nav className="gd-toc" aria-label="Содержание статьи">
      <div className="gd-toc-label">Содержание</div>
      <ul>
        {headings.map((h) => (
          <li key={h.id}>
            <a href={`#${h.id}`} className={activeId === h.id ? 'active' : ''}>
              {h.text}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
};
