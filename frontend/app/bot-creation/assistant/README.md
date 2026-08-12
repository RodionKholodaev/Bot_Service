# ИИ-помощник — фронтенд

Панель ИИ-помощника на странице создания бота: чат, который видит текущее
состояние формы и предлагает конкретные значения полей.

**Документация лежит в [`docs/ai-assistant/`](../../../../docs/ai-assistant/):**

- [README.md](../../../../docs/ai-assistant/README.md) — обзор, быстрый старт, карта файлов
- [frontend.md](../../../../docs/ai-assistant/frontend.md) — разбор этой папки
- [backend.md](../../../../docs/ai-assistant/backend.md) — серверная часть
- [how-to.md](../../../../docs/ai-assistant/how-to.md) — рецепты доработки и отладка

Чтобы помощник появился на странице, нужен ключ AITunnel в `backend/.env`
(`AITUNNEL_API_KEY`). Без него `GET /assistant/status` вернёт `enabled: false`,
и страница создания бота работает как раньше.
