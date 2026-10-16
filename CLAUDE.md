# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Pendel is a self-hosted work time tracker (home office vs. office days, commute tracking, flexitime balance). Multi-user from the start; meant to be published later.

## Layout

- `backend/` – FastAPI + SQLAlchemy 2 + SQLite (Alembic for migrations). Package `pendel`. All HTTP endpoints live under `/api`; in production the backend also serves the built SPA (`PENDEL_STATIC_DIR`) with an `index.html` fallback for client-side routes (`pendel/main.py`).
- `frontend/` – SvelteKit (Svelte 5 runes) as a pure SPA (`adapter-static`, `ssr = false`), Tailwind CSS 4, i18n via Paraglide (`messages/de.json`, `messages/en.json`; German is the base locale, no locale in URLs). The dev server proxies `/api` to `127.0.0.1:8000`.
- `Containerfile` – multi-stage build producing one image (frontend build copied into the Python image), data in `/data`.

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
