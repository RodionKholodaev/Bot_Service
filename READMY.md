# CryptoBot — Платформа для автоматической торговли


### 1. Бэкенд (FastAPI)

#### Создать и активировать виртуальное окружение

```bash
cd backend

# Создать окружение
python -m venv venv

# Активировать — macOS / Linux
source venv/bin/activate

# Активировать — Windows
venv\Scripts\activate
```

#### Установить зависимости

```bash
pip install -r requirements.txt
```


#### Запустить сервер

```bash
uvicorn src.main:app --reload
```

Бэкенд запустится на **http://localhost:8000**
Документация API (Swagger): **http://localhost:8000/docs**

---

### 2. Фронтенд (Next.js)

```bash
cd frontend

# Установить зависимости
npm install

# Запустить dev-сервер
npm run dev
```

Фронтенд запустится на **http://localhost:3000**

> Запросы с фронтенда на `/api/*` автоматически проксируются на бэкенд через `next.config.ts`

---

### 3. Запуск обоих серверов одновременно

Открой **два терминала**:

```bash
# Терминал 1 — бэкенд
cd backend && source venv/bin/activate && uvicorn src.main:app --reload

# Терминал 2 — фронтенд
cd frontend && npm run dev
```
