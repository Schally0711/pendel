# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Pendel is a self-hosted work time tracker (home office vs. office days, commute tracking, flexitime balance). Multi-user from the start; meant to be published later.

## Layout

- `backend/` – FastAPI + SQLAlchemy 2 + SQLite (Alembic for migrations). Package `pendel`. All HTTP endpoints live under `/api`; in production the backend also serves the built SPA (`PENDEL_STATIC_DIR`) with an `index.html` fallback for client-side routes (`pendel/main.py`).
- `frontend/` – SvelteKit (Svelte 5 runes) as a pure SPA (`adapter-static`, `ssr = false`), Tailwind CSS 4, i18n via Paraglide (`messages/de.json`, `messages/en.json`; German is the base locale, no locale in URLs). The dev server proxies `/api` to `127.0.0.1:8000`.
- `deploy/` – `build-release.sh` (tarball with wheel + built SPA + installer into `dist/`), `install.sh` (idempotent install/update on Debian: user `pendel`, venv in `/opt/pendel`, data `/var/lib/pendel`, env `/etc/pendel/pendel.env`, health check), `pendel.service` (hardened systemd unit, uvicorn with proxy headers).
- PWA: `static/manifest.webmanifest`, icons rendered from `frontend/assets/icon.svg` via `assets/render-icons.py` (Playwright), `src/service-worker.ts` caches the app shell only, never `/api/`. SvelteKit 3 removed `$service-worker`: use `$app/manifest` (`immutable`, `assets`) and `$app/env` (`version`). Backend serves `index.html`, `service-worker.js`, `manifest.webmanifest` with `Cache-Control: no-cache`.
- `Containerfile` – multi-stage build producing one image (frontend build copied into the Python image), data in `/data`.

## Auth & API

- First run: `POST /api/setup` creates the admin (only while no user exists). Further users only via admin invitation links (`/invite/<token>`); no open registration.
- Browser auth = session cookie (`pendel_session`, token hashed in `login_sessions`). Automations use `Authorization: Bearer <api token>`.
- CSRF guard (`main.py`): cookie-authenticated POST/PUT/PATCH/DELETE under `/api/` must send `X-Requested-With: pendel` (the frontend `api.ts` client does this; tests set it as default header).
- Every user-owned row is loaded via `api/common.owned()` → 404 for other users' data.
- `/api/today` and `/api/report` feed the UI; the balance ignores days after the user's local today.

## Frontend structure

- Imports use Node subpath imports `#lib/...` (SvelteKit 3; no `$lib`). TS modules need the `.js` suffix (`#lib/api.js`), components the `.svelte` suffix.
- `lib/labels.ts` holds labels/colours for day and place kinds – use it instead of local maps.
- `lib/api.ts` (fetch wrapper, redirects to /login on 401), `lib/session.svelte.ts` (current user, rune state), `lib/time.ts` (all date math in the *user's* time zone: `zonedToIso`, `localDate`, `localTime`), `lib/types.ts` mirrors `schemas.py`.
- Routes: `/` today (clock actions, live timer), `/history` month view + `DayEditor` modal, `/absences` (vacation account, range entry with dry-run preview, year calendar), `/settings`, `/admin`, public `/login`, `/setup`, `/invite/[token]`. The root layout gates non-public routes.
- Styling: Tailwind 4 with custom utilities (`card`, `btn-*`, `input`, `label`, `muted`) defined via `@utility` in `routes/layout.css` (Tailwind 4 cannot `@apply` classes from `@layer components`). Brand colors `brand-*`, place colors `home`/`office`/`travel`. Dark mode follows the OS.
- Local cookies: run the backend with `PENDEL_SECURE_COOKIES=false` when testing over plain HTTP on a non-localhost address.

## Backend architecture

- `models.py` – SQLAlchemy models. Timestamps are UTC (`dbtypes.UTCDateTime`, rejects naive datetimes); sessions and commutes belong to the *local* day (user time zone) on which they start. Running entries have `end = None`.
- `calc.py` – pure accounting rules on plain dataclasses, no DB: day target (holidays/vacation/sick are neutral, flex days keep the target), break handling (`manual` vs. `auto` = fixed daily break, longer recorded breaks win; breaks with `deducted = False` are recorded absences that count as work, e.g. customer visits; office gaps up to `office_gap_break_max_minutes` are breaks), ArbZG warnings, commute credit percentage.
- `reports.py` – loads a user's data for a date range and feeds `calc.evaluate_day`; holidays via the `holidays` package (country + subdivision from the user). The flexitime balance is never stored: `balance()` = sum of `BalanceAdjustment` (opening balance, payouts) + daily diffs since the first `WorkModel`.
- `WorkModel` rows are versioned by `valid_from`; the newest model not after a day applies to it, so contract changes keep past days correct.
- Absences: `DayEntry` per day (`DayKind`); `models.NEUTRAL_DAY_KINDS` make a day neutral (target 0), `FLEX_DAY` keeps the target, `VACATION_HALF` halves it. `absences.py` books ranges only on workdays (target > 0 and no holiday, via `reports.schedule`, which falls back to the first work model for earlier days), groups entries into periods and computes the yearly `VacationAllowance` account (taken ≤ today, planned after).
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
