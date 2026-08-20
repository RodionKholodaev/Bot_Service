# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Bot_Service is a platform for creating and running automated crypto trading bots. A user connects an exchange API key (currently **Bybit** only), picks a trading pair, leverage, direction (long/short/both), and a strategy — either a simplified preset (conservative/moderate/aggressive) or manually chosen indicator conditions (RSI, CCI) — plus take-profit and an optional stop-loss. The service then generates a config and strategy file and launches the bot as its own **freqtrade** Docker container. Bots can run in `dry_run` (simulation, no real orders) or live with a real exchange key. The product priority is simplicity for non-technical users — do not add complexity (new indicators, config options, abstractions) beyond what's asked.

## Architecture

- **Backend**: Python, FastAPI, async SQLAlchemy 2.0 (`Mapped`/`mapped_column`), Pydantic Settings. Single Uvicorn process, entry point `backend/src/main.py`. No Celery/queue — all backend concurrency is one asyncio process: FastAPI request handlers + a single background `asyncio.create_task()`.
- **Frontend**: Next.js 16 / React 19 / TypeScript in `frontend/`, chart.js for stats.
- **Bots are not code in this repo** — each bot is a separate Docker container running `freqtradeorg/freqtrade:stable`, managed imperatively via the Docker SDK (`backend/src/services/docker_manager.py`), no docker-compose/k8s. `BotService.create_bot()`/`start_bot()` render a strategy `.py` file from `backend/src/templates/multifilter_strategy.template` (string `.replace()` + `repr()`, no sandboxing) and a `config.json` from `templates/config.template.json`, then launch the container. Each bot gets its own port (`BOT_API_PORT_RANGE_START`–`END`, default 9000–9999), its own freqtrade REST API with basic auth, and its own SQLite `tradesv3.sqlite` inside the container — **the backend never talks to the exchange directly**, only to each bot's freqtrade REST API.
- **DB**: **SQLite (`aiosqlite`) everywhere** — local dev, tests, and the server (`DATABASE_URL`, default `sqlite+aiosqlite:///./cryptobot.db`). PostgreSQL is under consideration but not in use; `asyncpg` is not installed, and the `psycopg2-binary` in `requirements.txt` is a sync driver that `create_async_engine` rejects. Two consequences of SQLite that are live right now: **foreign keys are not enforced** (`PRAGMA foreign_keys = 0`, so every `ondelete="CASCADE"` in the models is a no-op — deleting a user leaves its bots/trades orphaned), and only one writer at a time (run a single uvicorn process, or expect `database is locked`). Schema is managed by **alembic** (`backend/alembic/`, config in `backend/alembic.ini`) — `main.py`'s `lifespan()` no longer calls `Base.metadata.create_all()`, so a fresh DB (new dev machine, new prod deploy) needs `alembic upgrade head` run once before the app can start. `alembic/env.py` builds `target_metadata` from `Base` and auto-imports every module in `src/models/` via `pkgutil` — deliberately not a hand-written import list, because a forgotten import makes autogenerate *silently* skip the table (that's how `balance_transactions` ended up missing from the dev DB). A new model still needs a normal import somewhere on the `src.main` path for the tests' `create_all`/`clear_database` to see it. Migrations run in batch mode (`render_as_batch=True`) — required, since SQLite can't `ALTER TABLE`; harmless if Postgres ever happens. When you change a model: `alembic revision --autogenerate -m "..."`, then **read the generated file by hand** before committing — autogenerate misses renames and some type changes.
- **The only backend "bot loop"**: `services/polling_worker.py` — an infinite `while True` loop (started via `asyncio.create_task()` in `lifespan()`), polling every `POLL_INTERVAL = 30s`. Each cycle: fetch all `status="running"` bots → GET `/api/v1/trades` from each bot's own freqtrade container (hardcoded `http://127.0.0.1:{bot.api_port}`, note this ignores `settings.BOT_API_HOST` used elsewhere — known inconsistency) → diff against the local `trades` table → create/update rows → run `CommissionService.process_commission()` on newly-closed trades. Wrapped in nested try/except so one bad bot/DB error doesn't kill the whole worker.

## Key modules (`backend/src/`)

- `services/bot_service.py` — create/start/stop/delete a bot; writes `Bot.status`/`Bot.error_message`.
- `services/strategy_presets.py` — the `PRESETS` dict (conservative/moderate/aggressive) and `resolve_filters()`.
- `services/stats_service.py` — pure DB-reader (no network), computes P&L chart, max drawdown (deepest fall from the equity curve's peak, in % of that peak — the curve starts at the invested capital: a bot's `stake_amount`, or their sum for a portfolio), winrate, portfolio stats. **A trade with `profit_usdt == 0` counts as a loss**, not neutral (`profit <= 0`) — easy to get wrong by hand, see `backend/tests/unit/test_stats_service.py` for the locked-down behavior and the fake-repo pattern used to test it without a DB.
- `services/commission_service.py` — charges the service commission on profitable closed trades against `User.service_balance`, using `services/exchange_rate_service.py` for the USDT/RUB rate.
- `services/payment_service.py` — YooKassa (RUB) top-ups; webhook validates caller IP against a hardcoded whitelist.
- `core/telegram_alerts.py` — a `logging.Handler` that ships **only `CRITICAL`-level** logs to a developer Telegram chat (deduped 5 min per identical message). Deliberately not wired to `ERROR`/`.exception()` — those are used throughout for expected, self-healing failures (e.g. one bot's container briefly unreachable) and would be noise. To add a new alert-worthy condition, call `logger.critical(...)` at that call site — don't touch this file. Enabled only if `TELEGRAM_ALERT_BOT_TOKEN`/`TELEGRAM_ALERT_CHAT_ID` are set in `.env`.
- `logger_config.py` — `setup_logging()`: `ExtraFormatter` renders `extra={...}` fields into the log line (plain `logging.basicConfig` silently drops them), plus a `RotatingFileHandler` writing to `backend/logs/app.log` in addition to stdout. `extra_fields(record)` is the shared helper both this and `telegram_alerts.py` use.
- `models/` — `Bot` (UUID id, `status`: created/starting/running/stopped/error, `dry_run` bool, `container_id`/`api_port`/`api_username`/`api_password`, `total_profit` incrementally maintained), `Trade` (`freqtrade_trade_id` is the dedup key against freqtrade, `profit_usdt`/`profit_pct`, `commission_usdt`/`rub`), `User` (`service_balance`, `commission_rate`), `ExchangeApiKey` (Fernet-encrypted). `BalanceTransaction` model **exists but is unused** — balance changes mutate `User.service_balance` directly, no ledger/audit trail.
- `core/exceptions.py` + `core/exception_handlers.py` — domain exceptions (`BadRequestError`, `ForbiddenError`, `NotFoundError`, `ConflictError`, `PaymentRequiredError`, `UnauthorizedError`) map to JSON `{"detail": ...}`.

## Conventions

- **Log messages in English**, `extra={...}` dict for structured context (`bot_id`, `user_id`, etc.), `logger.exception()` inside `except` blocks for the traceback, `logger.critical()` reserved for things that should page the developer (see `telegram_alerts.py` above) — don't casually bump something to `critical`.
- **User-facing error text (HTTP `detail`) is in Russian**; that's the existing split, keep it.
- Known gaps worth knowing about before touching related code: exchange-level errors (insufficient balance, rate limits, bad API key) are currently only visible in raw freqtrade container logs (`GET /bots/{id}/logs`) — the backend doesn't parse/classify them. `Bot.total_profit` and the sum of `Trade.profit_usdt` are two independent running totals that can drift.

## Testing

Full guide: `docs/testing/README.md` (structure, layers, patterns, blind spots) and `docs/testing/how-to.md` (recipes: add a test, fake the network/Docker/DB, debug). CI (see **CI & tooling** below) runs `pytest`, but still run `python -m pytest` from `backend/` yourself before calling work done — CI only fires on push.

99 tests, ~6s, in `backend/tests/{unit,integration,fakes}/`. `pytest` + `pytest-asyncio`, `asyncio_mode = auto` (so `@pytest.mark.asyncio` isn't required — but it's on every async test, keep it). Unit tests are the main layer and touch neither DB nor network; `tests/integration/` is a deliberately thin layer hitting the real app via `httpx.AsyncClient(ASGITransport)` against a throwaway SQLite DB — put business logic in unit tests, not there. Note `tests/fakes/test_user_repository.py` is a reusable fake, not a test file, despite the `test_` prefix.

**Style, applied consistently across all five test files:** module docstring saying what's tested and why it's fake-based; literal `# Arrange` / `# Act` / `# Assert` comments; file-local `make_bot()`/`make_trade()`/`make_user()` factories with keyword-only args instead of restating every required model field; hand-written `Fake*`/`Spy*` classes with a docstring naming what they replace — **`unittest.mock` is not used here, don't introduce it**. Test names are English assertions (`test_zero_profit_trade_counts_as_loss`); docstrings and comments are Russian; any non-obvious `assert` carries a comment with the arithmetic or the reason.

**A new test must be shown to fail.** Break the line it covers, confirm red, restore. The suite is mutation-audited (last run: 23 mutations, all caught). Tests passing for the wrong reason have already happened here — a "unknown field is dropped" test stayed green after the allowlist was removed, because a second guard downstream masked it.

**Traps, each of which has silently broken a test in this repo:**
- `tests/conftest.py` calls `sentry_sdk.init(dsn="")` **before** importing `src.main` — `src.main` initializes Sentry with the production DSN at import time, so reordering those lines ships `logger.critical` from tests to the real Glitchtip.
- `monkeypatch.setattr` must target the module that **imported** a name (`src.services.commission_service.ExchangeRateService`), not the one defining it.
- A column `default=...` is applied by a real INSERT, and the fake session's `flush()` is a no-op — on an unflushed object `commission_paid` is `None`, not `False`. Assert `not trade.commission_paid`.
- `FakeTradeRepo` in `test_stats_service.py` returns its list regardless of the query, so ordering/filtering is invisible in results — `_FakeQuery` records `.where()`/`.order_by()` calls and those are asserted separately (compare `str()` of the expression; SQLAlchemy objects don't compare with `==`).
- `clear_database` walks `reversed(Base.metadata.sorted_tables)`, so a new model must be imported somewhere on the `src.main` path or it will be neither created nor cleaned between tests.
- `ASGITransport` does not run `lifespan()` — `polling_worker` is never exercised by tests. Tests don't use alembic either: `tests/conftest.py` builds its own schema straight from `Base.metadata.create_all()`/`drop_all()` against the throwaway test DB, independent of migration history.

**Not covered at all** — a green suite says nothing about: `payment_service` (YooKassa, webhook IP whitelist), `bot_service` (create/start/stop/delete), `exchange_api_key` Fernet encryption, `strategy_presets`, `get_portfolio_stats`/`get_home_stats`, `lifespan()`, and bot behavior itself (no testnet — dry-run by hand only).

**Behaviors deliberately locked by tests — don't "fix" them:** a `profit_usdt == 0` trade counts as a loss; `_max_drawdown` returns `None` only when there are no trades or the invested capital is unknown (`None`/`0.0`) — a bot that never went positive still gets a real drawdown; `process_commission` is idempotent — `trade.commission_paid` means "trade accounted for", not "commission charged", so it is set on losing and zero-profit trades too, and the early `return` it guards protects `Bot.total_profit` from double-counting as well (commission is still charged strictly on `profit > 0`). The tests document these as current behavior, not as endorsements.

## CI & tooling

`.github/workflows/tests.yml` runs on every push, four jobs: `test` (pytest), `lint-backend` (ruff + pip-audit), `frontend` (eslint + prettier + `next build` + npm audit), `secrets-scan` (gitleaks over the whole repo). `test` and `lint-backend` are hard gates; `frontend`'s ESLint step and both jobs' dependency-audit steps run with `continue-on-error: true` — see below for why.

- **Ruff** (`backend/pyproject.toml`) replaces flake8/isort/pyupgrade/bandit in one tool: `E,F,I,B,C4,UP,ASYNC,S` rule sets, `line-length = 120`, `E501` ignored (formatting handles it, Russian-text strings run long). `B008` (function call in argument default) is ignored globally — it's FastAPI's own `Depends(...)` idiom, not a bug. `tests/conftest.py` gets a per-file `E402` ignore because its `sentry_sdk.init(dsn="")` must run before the `src.config` import (see Testing traps above) — don't "fix" that ordering. When SQLAlchemy boolean columns need a `.where()` filter, use `Column.is_(True)`, not `== True` — `ruff`'s own E712 fix (bare `Column` truthiness) does not generate SQL and would silently break the query.
- **pip-audit** checks `requirements.txt` against known CVEs. Currently flags `cryptography==49.0.0` (fix: 50.0.0 — this is what encrypts `ExchangeApiKey`, worth upgrading deliberately with a test pass, not an automated bump) and `ecdsa==0.19.2` (no fix — upstream has declared the side-channel timing issue out of scope; accepted risk, not actionable).
- **Prettier** (`frontend/.prettierrc.json`, `singleQuote: true` to match existing code) and **eslint-plugin-security** (wired into `frontend/eslint.config.mjs` via `security.configs.recommended`) are new; `npm run format` / `npm run format:check` are new scripts.
- **`npm run lint` is not a hard CI gate yet** — it already had 14 pre-existing errors (mostly `react-hooks/set-state-in-effect` in `auth`/`home`/`settings`/`stats`/`feedback`/`bot-creation` pages, from `eslint-config-next`'s React Compiler rules, unrelated to this tooling setup) that were never caught because lint never ran in CI before. Fixing them means touching live `useEffect`/`setState` logic in auth-adjacent pages and needs a browser test pass, not a blind autofix — flip `continue-on-error` off once they're fixed. `eslint-plugin-security`'s `detect-object-injection` rule also produced 11 warnings (not blocking) — likely mostly false positives on `obj[key]` indexing, unreviewed so far.
- **npm audit** on the frontend is non-blocking for the same reason `cryptography` isn't auto-bumped: the flagged CVEs are in `next`/`postcss`/`sharp`, and the fix requires bumping `next` past the exact-pinned `16.2.4` (see `frontend/AGENTS.md` — a deliberately pinned non-standard preview build). `npm audit fix` (no `--force`) is safe to run any time; `--force` is not.
- **gitleaks** (`gitleaks/gitleaks-action@v2`) scans the whole repo on every push for committed secrets — relevant here given Fernet-encrypted exchange keys, Telegram bot tokens, and YooKassa credentials.

## Commands

Backend (from `backend/`):
```
pip install -r requirements.txt
alembic upgrade head                   # apply migrations — needed once before first run on a fresh DB
uvicorn src.main:app --reload          # dev server
python -m pytest                       # full test suite
python -m pytest tests/unit/test_stats_service.py -v   # single file
python -m pytest tests/unit/test_stats_service.py::test_max_drawdown_calculates_percent_from_peak  # single test
python -m pytest -k commission          # by name
ruff check .                           # lint
ruff format .                          # format
pip-audit -r requirements.txt          # dependency CVE scan
```
See **Testing** below before writing or changing tests.

Full DB guide: `docs/database/README.md` (tables, relations, alembic setup, gotchas) and `docs/database/how-to.md` (recipes: change a model, first start on a server, rollback, symptom→cause table).

Migrations (from `backend/`), after changing a model in `src/models/`:
```
alembic revision --autogenerate -m "add X to bots"   # generate, then read the diff by hand
alembic upgrade head                                  # apply locally
alembic downgrade -1                                  # undo the last migration
alembic history                                        # list all revisions
alembic current                                        # what revision is this DB at
```

Frontend (from `frontend/`):
```
npm run dev
npm run build
npm run lint
npm run format          # prettier --write
npm run format:check    # prettier --check, used in CI
npm audit                # dependency CVE scan
```
