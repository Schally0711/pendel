# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Pendel is a self-hosted work time tracker (home office vs. office days, commute tracking, flexitime balance). Multi-user from the start; meant to be published later.

## Layout

- `backend/` – FastAPI + SQLAlchemy 2 + SQLite (Alembic for migrations). Package `pendel`. All HTTP endpoints live under `/api`; in production the backend also serves the built SPA (`PENDEL_STATIC_DIR`) with an `index.html` fallback for client-side routes (`pendel/main.py`).
- `frontend/` – SvelteKit (Svelte 5 runes) as a pure SPA (`adapter-static`, `ssr = false`), Tailwind CSS 4, i18n via Paraglide (`messages/de.json`, `messages/en.json`; German is the base locale, no locale in URLs). The dev server proxies `/api` to `127.0.0.1:8000`.
- `Containerfile` – multi-stage build producing one image (frontend build copied into the Python image), data in `/data`.

## Backend architecture

- `models.py` – SQLAlchemy models. Timestamps are UTC (`dbtypes.UTCDateTime`, rejects naive datetimes); sessions and commutes belong to the *local* day (user time zone) on which they start. Running entries have `end = None`.
- `calc.py` – pure accounting rules on plain dataclasses, no DB: day target (holidays/vacation/sick are neutral, flex days keep the target), break handling (`manual` vs. `auto` = fixed daily break, longer recorded breaks win; breaks with `deducted = False` are recorded absences that count as work, e.g. customer visits; office gaps up to `office_gap_break_max_minutes` are breaks), ArbZG warnings, commute credit percentage.
- `reports.py` – loads a user's data for a date range and feeds `calc.evaluate_day`; holidays via the `holidays` package (country + subdivision from the user). The flexitime balance is never stored: `balance()` = sum of `BalanceAdjustment` (opening balance, payouts) + daily diffs since the first `WorkModel`.
- `WorkModel` rows are versioned by `valid_from`; the newest model not after a day applies to it, so contract changes keep past days correct.
- `Event` stores raw automation events (zone enter/leave, …) for traceability; sessions/commutes are derived from them. `ApiToken` stores only token hashes.
- Migrations live in `pendel/migrations` (shipped inside the package) and run automatically on startup (`db.migrate()`). After changing models: `PENDEL_DATA_DIR=/tmp/x .venv/bin/alembic upgrade head && PENDEL_DATA_DIR=/tmp/x .venv/bin/alembic revision --autogenerate -m "..."`, then review the generated file (`render_as_batch` is on for SQLite).

## Commands

```bash
# backend (from backend/)
.venv/bin/uvicorn pendel.main:app --reload
.venv/bin/pytest                       # all tests
.venv/bin/pytest tests/test_health.py::test_health   # single test
.venv/bin/ruff check . && .venv/bin/ruff format .

# frontend (from frontend/)
npm run dev
npm run check                          # compiles i18n messages, then svelte-check
npm run build
```

## Conventions

- Code, comments, commits and docs in English; every user-facing string goes through Paraglide (`m.<key>()`) with both `de` and `en` entries.
- Settings come from env vars with prefix `PENDEL_` (`pendel/config.py`); DB access through the `get_db` dependency.
- Tests use a temporary `PENDEL_DATA_DIR` (see `tests/conftest.py`) – never touch a real database.
