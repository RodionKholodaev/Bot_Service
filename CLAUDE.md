# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Bot_Service is a platform for creating and running automated crypto trading bots. A user connects an exchange API key (currently **Bybit** only), picks a trading pair, leverage, direction (long/short/both), and a strategy — either a simplified preset (conservative/moderate/aggressive) or manually chosen indicator conditions (RSI, CCI) — plus take-profit and an optional stop-loss. The service then generates a config and strategy file and launches the bot as its own **freqtrade** Docker container. Bots can run in `dry_run` (simulation, no real orders) or live with a real exchange key. The product priority is simplicity for non-technical users — do not add complexity (new indicators, config options, abstractions) beyond what's asked.

## Architecture

- **Backend**: Python, FastAPI, async SQLAlchemy 2.0 (`Mapped`/`mapped_column`), Pydantic Settings. Single Uvicorn process, entry point `backend/src/main.py`. No Celery/queue — all backend concurrency is one asyncio process: FastAPI request handlers + a single background `asyncio.create_task()`.
- **Frontend**: Next.js 16 / React 19 / TypeScript in `frontend/`, chart.js for stats.
- **Bots are not code in this repo** — each bot is a separate Docker container running `freqtradeorg/freqtrade:stable`, managed imperatively via the Docker SDK (`backend/src/services/docker_manager.py`), no docker-compose/k8s. `BotService.create_bot()`/`start_bot()` render a strategy `.py` file from `backend/src/templates/multifilter_strategy.template` (string `.replace()` + `repr()`, no sandboxing) and a `config.json` from `templates/config.template.json`, then launch the container. Each bot gets its own port (`BOT_API_PORT_RANGE_START`–`END`, default 9000–9999), its own freqtrade REST API with basic auth, and its own SQLite `tradesv3.sqlite` inside the container — **the backend never talks to the exchange directly**, only to each bot's freqtrade REST API.
- **DB**: PostgreSQL in prod (`DATABASE_URL`), SQLite (`aiosqlite`) in tests. `alembic` is a listed dependency but **there are no migrations** — schema is created via `Base.metadata.create_all()` in `main.py`'s `lifespan()`. If you change a model, there's no migration to write, but also no safety net on schema drift.
- **The only backend "bot loop"**: `services/polling_worker.py` — an infinite `while True` loop (started via `asyncio.create_task()` in `lifespan()`), polling every `POLL_INTERVAL = 30s`. Each cycle: fetch all `status="running"` bots → GET `/api/v1/trades` from each bot's own freqtrade container (hardcoded `http://127.0.0.1:{bot.api_port}`, note this ignores `settings.BOT_API_HOST` used elsewhere — known inconsistency) → diff against the local `trades` table → create/update rows → run `CommissionService.process_commission()` on newly-closed trades. Wrapped in nested try/except so one bad bot/DB error doesn't kill the whole worker.

## Key modules (`backend/src/`)

- `services/bot_service.py` — create/start/stop/delete a bot; writes `Bot.status`/`Bot.error_message`.
- `services/strategy_presets.py` — the `PRESETS` dict (conservative/moderate/aggressive) and `resolve_filters()`.
- `services/stats_service.py` — pure DB-reader (no network), computes P&L chart, max drawdown (as % of peak cumulative profit), winrate, portfolio stats. **A trade with `profit_usdt == 0` counts as a loss**, not neutral (`profit <= 0`) — easy to get wrong by hand, see `backend/tests/unit/test_stats_service.py` for the locked-down behavior and the fake-repo pattern used to test it without a DB.
- `services/commission_service.py` — charges the service commission on profitable closed trades against `User.service_balance`, using `services/exchange_rate_service.py` for the USDT/RUB rate.
- `services/payment_service.py` — YooKassa (RUB) top-ups; webhook validates caller IP against a hardcoded whitelist.
- `core/telegram_alerts.py` — a `logging.Handler` that ships **only `CRITICAL`-level** logs to a developer Telegram chat (deduped 5 min per identical message). Deliberately not wired to `ERROR`/`.exception()` — those are used throughout for expected, self-healing failures (e.g. one bot's container briefly unreachable) and would be noise. To add a new alert-worthy condition, call `logger.critical(...)` at that call site — don't touch this file. Enabled only if `TELEGRAM_ALERT_BOT_TOKEN`/`TELEGRAM_ALERT_CHAT_ID` are set in `.env`.
- `logger_config.py` — `setup_logging()`: `ExtraFormatter` renders `extra={...}` fields into the log line (plain `logging.basicConfig` silently drops them), plus a `RotatingFileHandler` writing to `backend/logs/app.log` in addition to stdout. `extra_fields(record)` is the shared helper both this and `telegram_alerts.py` use.
- `models/` — `Bot` (UUID id, `status`: created/starting/running/stopped/error, `dry_run` bool, `container_id`/`api_port`/`api_username`/`api_password`, `total_profit` incrementally maintained), `Trade` (`freqtrade_trade_id` is the dedup key against freqtrade, `profit_usdt`/`profit_pct`, `commission_usdt`/`rub`), `User` (`service_balance`, `commission_rate`), `ExchangeApiKey` (Fernet-encrypted). `BalanceTransaction` model **exists but is unused** — balance changes mutate `User.service_balance` directly, no ledger/audit trail.
- `core/exceptions.py` + `core/exception_handlers.py` — domain exceptions (`BadRequestError`, `ForbiddenError`, `NotFoundError`, `ConflictError`, `PaymentRequiredError`, `UnauthorizedError`) map to JSON `{"detail": ...}`.

## Conventions

- **Log messages in English**, `extra={...}` dict for structured context (`bot_id`, `user_id`, etc.), `logger.exception()` inside `except` blocks for the traceback, `logger.critical()` reserved for things that should page the developer (see `telegram_alerts.py` above) — don't casually bump something to `critical`.
- **User-facing error text (HTTP `detail`) is in Russian**; that's the existing split, keep it.
- Known gaps worth knowing about before touching related code: exchange-level errors (insufficient balance, rate limits, bad API key) are currently only visible in raw freqtrade container logs (`GET /bots/{id}/logs`) — the backend doesn't parse/classify them. `Bot.total_profit` and the sum of `Trade.profit_usdt` are two independent running totals that can drift. There is no CI.

## Commands

Backend (from `backend/`):
```
pip install -r requirements.txt
uvicorn src.main:app --reload          # dev server
python -m pytest                       # full test suite
python -m pytest tests/unit/test_stats_service.py -v   # single file
python -m pytest tests/unit/test_stats_service.py::test_max_drawdown_calculates_percent_from_peak  # single test
```
Tests: `pytest` + `pytest-asyncio` (`asyncio_mode = auto`, no `@pytest.mark.asyncio` strictly required but used for consistency), `backend/tests/{unit,integration,fakes}/`. Pattern: Arrange/Act/Assert with comments, fake repositories instead of a real DB for services (`tests/fakes/`, `test_comission_service.py`, `test_stats_service.py`); integration tests hit the real app through `httpx.AsyncClient(ASGITransport)` against a throwaway SQLite DB (`tests/conftest.py`). No testnet access — bot-behavior testing is dry-run only.

Frontend (from `frontend/`):
```
npm run dev
npm run build
npm run lint
```
