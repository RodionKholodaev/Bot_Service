'use client';

import React from 'react';

/** Минимальный markdown под ответы ассистента: абзацы, списки, **жирный**, `код`.
 *  Намеренно без библиотеки и без dangerouslySetInnerHTML — рендерим React-узлами,
 *  так что вставить разметку через ответ модели невозможно. */

const INLINE = /(\*\*[^*]+\*\*|`[^`]+`)/g;

function renderInline(text: string, keyPrefix: string): React.ReactNode[] {
  return text.split(INLINE).filter(Boolean).map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={key}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={key}>{part.slice(1, -1)}</code>;
    }
    return <React.Fragment key={key}>{part}</React.Fragment>;
  });
}

type Block =
  | { kind: 'p'; lines: string[] }
  | { kind: 'ul'; items: string[] }
  | { kind: 'ol'; items: string[] };

function toBlocks(source: string): Block[] {
  const blocks: Block[] = [];

  for (const rawLine of source.split('\n')) {
    const line = rawLine.trimEnd();
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    const last = blocks[blocks.length - 1];

    if (bullet) {
      if (last?.kind === 'ul') last.items.push(bullet[1]);
      else blocks.push({ kind: 'ul', items: [bullet[1]] });
      continue;
    }
    if (numbered) {
      if (last?.kind === 'ol') last.items.push(numbered[1]);
      else blocks.push({ kind: 'ol', items: [numbered[1]] });
      continue;
    }
    if (!line.trim()) {
      // Пустая строка закрывает текущий блок
      if (last?.kind === 'p' && last.lines.length) blocks.push({ kind: 'p', lines: [] });
      continue;
    }

    const clean = line.replace(/^#{1,6}\s+/, '');
    if (last?.kind === 'p') last.lines.push(clean);
    else blocks.push({ kind: 'p', lines: [clean] });
  }

  return blocks.filter((b) => (b.kind === 'p' ? b.lines.length > 0 : b.items.length > 0));
}

export const Markdown = ({ text }: { text: string }) => (
  <div className="ai-markdown">
    {toBlocks(text).map((block, i) => {
      if (block.kind === 'ul') {
        return (
          <ul key={i}>
            {block.items.map((item, j) => (
              <li key={j}>{renderInline(item, `${i}-${j}`)}</li>
            ))}
          </ul>
        );
      }
      if (block.kind === 'ol') {
        return (
          <ol key={i}>
            {block.items.map((item, j) => (
              <li key={j}>{renderInline(item, `${i}-${j}`)}</li>
            ))}
          </ol>
        );
      }
      return <p key={i}>{renderInline(block.lines.join(' '), String(i))}</p>;
    })}
  </div>
);
