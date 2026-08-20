import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { ChevronRight, Clock, ArrowLeft, ArrowRight, MessageCircle } from 'lucide-react';

import { GuidesShell } from '../GuidesShell';
import { GuideToc } from '../GuideToc';
import { GUIDES, CATEGORIES, getGuide, getNeighbours } from '../meta';
import { CONTENT } from '../content';

/* Страница одной статьи.
 *
 * Осознанно серверная: только так работают generateStaticParams (все статьи
 * уезжают в статику на сборке) и generateMetadata (нормальный заголовок и
 * описание, когда ссылку на гайд кидают в мессенджер). Интерактив тут ровно
 * два клиентских островка — шапка с балансом и оглавление. */

export function generateStaticParams() {
  return GUIDES.map((g) => ({ slug: g.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const guide = getGuide(slug);
  if (!guide) return { title: 'Статья не найдена — CryptoBot' };
  return {
    title: `${guide.title} — Обучение CryptoBot`,
    description: guide.description,
  };
}

export default async function GuideArticlePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const guide = getGuide(slug);
  const Article = CONTENT[slug];

  // Мета без текста (или наоборот) — это рассинхрон meta.ts и content.tsx,
  // а не запрос несуществующей страницы. Показываем 404 в обоих случаях.
  if (!guide || !Article) notFound();

  const category = CATEGORIES.find((c) => c.id === guide.category);
  const { prev, next } = getNeighbours(slug);

  return (
    <GuidesShell>
      <main className="gd-article-main">
        {/* Хлебные крошки */}
        <div className="gd-crumbs">
          <Link href="/guides">Обучение</Link>
          <ChevronRight size={14} />
          {category && (
            <>
              <span>{category.title}</span>
              <ChevronRight size={14} />
            </>
          )}
          <span>{guide.title}</span>
        </div>

        {/* Заголовок */}
        <header className="gd-article-head">
          <h1>{guide.title}</h1>
          <p className="gd-article-desc">{guide.description}</p>
          <div className="gd-article-meta">
            <span>
              <Clock size={14} />
              {guide.readMinutes} мин чтения
            </span>
          </div>
        </header>

        {/* Текст + оглавление */}
        <div className="gd-article-layout">
          <article className="gd-body">
            <Article />
          </article>
          <GuideToc />
        </div>

        {/* Соседние статьи */}
        {(prev || next) && (
          <nav className="gd-article-nav">
            {prev && (
              <Link href={`/guides/${prev.slug}`} className="gd-nav-card">
                <ArrowLeft size={20} />
                <div>
                  <div className="gd-nav-card-label">Назад</div>
                  <div className="gd-nav-card-title">{prev.title}</div>
                </div>
              </Link>
            )}
            {next && (
              <Link href={`/guides/${next.slug}`} className="gd-nav-card next">
                <ArrowRight size={20} />
                <div>
                  <div className="gd-nav-card-label">Далее</div>
                  <div className="gd-nav-card-title">{next.title}</div>
                </div>
              </Link>
            )}
          </nav>
        )}

        {/* Подвал */}
        <section className="gd-article-foot">
          <p>
            <strong>Остались вопросы?</strong> Напишите нам — ответим
            в течение 2–4 часов в рабочее время.
          </p>
          <Link href="/support" className="gd-btn-primary">
            <MessageCircle size={17} />
            В поддержку
          </Link>
        </section>
      </main>
    </GuidesShell>
  );
}
