# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Pendel is a self-hosted work time tracker (home office vs. office days, commute tracking, flexitime balance). Multi-user from the start; meant to be published later.

## Layout

- `backend/` – FastAPI + SQLAlchemy 2 + SQLite (Alembic for migrations). Package `pendel`. All HTTP endpoints live under `/api`; in production the backend also serves the built SPA (`PENDEL_STATIC_DIR`) with an `index.html` fallback for client-side routes (`pendel/main.py`).
- `frontend/` – SvelteKit (Svelte 5 runes) as a pure SPA (`adapter-static`, `ssr = false`), Tailwind CSS 4, i18n via Paraglide (`messages/de.json`, `messages/en.json`; German is the base locale, no locale in URLs). The dev server proxies `/api` to `127.0.0.1:8000`.
- `deploy/` – `build-release.sh` (tarball with wheel + built SPA + installer into `dist/`), `install.sh` (idempotent install/update on Debian: user `pendel`, venv in `/opt/pendel`, data `/var/lib/pendel`, env `/etc/pendel/pendel.env`, health check), `pendel.service` (hardened systemd unit, uvicorn with proxy headers).
- PWA: `static/manifest.webmanifest`, icons rendered from `frontend/assets/icon.svg` via `assets/render-icons.py` (Playwright), manifest `shortcuts` (long-press on the app icon) open `/?action=start_home|start_office|stop`, which the today page runs once and then removes from the URL (icons rendered by the same script); `src/service-worker.ts` caches the app shell only, never `/api/`. SvelteKit 3 removed `$service-worker`: use `$app/manifest` (`immutable`, `assets`) and `$app/env` (`version`). Backend serves `index.html`, `service-worker.js`, `manifest.webmanifest` with `Cache-Control: no-cache`.
- `Containerfile` – multi-stage build producing one image (frontend build copied into the Python image), data in `/data`.

## Auth & API

- First run: `POST /api/setup` creates the admin (only while no user exists). Further users only via admin invitation links (`/invite/<token>`); no open registration.
- Browser auth = session cookie (`pendel_session`, token hashed in `login_sessions`, `last_seen_at` written at most every 5 min; `auth.current_session(request)` is the request's session). Automations use `Authorization: Bearer <api token>`.
- Login goes through `auth.login()`: Argon2id password check, rate limits per client address (`login_limiter`, all attempts) and per account (`account_limiter`, failures only), then the optional second factor. 2FA = TOTP (`totp.py`, stdlib RFC 6238, ±1 step, `users.totp_last_step` blocks replay) + 10 one-time recovery codes (hashed in `recovery_codes`); `401 totp_required` tells clients (login page, HA config flow via `/api/auth/token`) to ask for the code. Password change and enabling 2FA end all other sessions; admins can reset a user's 2FA (`DELETE /api/admin/users/{id}/totp`).
- Security headers middleware (`nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Cache-Control: no-store` on `/api/`).
- CSRF guard (`main.py`): cookie-authenticated POST/PUT/PATCH/DELETE under `/api/` must send `X-Requested-With: pendel` (the frontend `api.ts` client does this; tests set it as default header).
- Every user-owned row is loaded via `api/common.owned()` → 404 for other users' data.
- Instance settings (`instance.py`, table `app_settings`): `public_url` (admin UI, `PUT /api/admin/instance`; falls back to `PENDEL_PUBLIC_URL`) is the external base for invitation/calendar/HA links; the frontend reads it via `GET /api/instance` (`lib/instance.svelte.ts`, `instance.baseUrl`). Pendel works fully behind proxies/tunnels; trusted proxies = `PENDEL_FORWARDED_ALLOW_IPS` (uvicorn `--forwarded-allow-ips`).
- `/api/today` and `/api/report` feed the UI; the balance ignores days after the user's local today.

## Frontend structure

- Imports use Node subpath imports `#lib/...` (SvelteKit 3; no `$lib`). TS modules need the `.js` suffix (`#lib/api.js`), components the `.svelte` suffix.
- `lib/labels.ts` holds labels/colours for day and place kinds – use it instead of local maps.
- `lib/api.ts` (fetch wrapper, redirects to /login on 401), `lib/session.svelte.ts` (current user, rune state), `lib/time.ts` (all date math in the *user's* time zone: `zonedToIso`, `localDate`, `localTime`), `lib/types.ts` mirrors `schemas.py`.
- Routes: `/` today (clock actions, live timer), `/history` month view + `DayEditor` modal, `/stats` (charts in `lib/charts/*` – plain SVG, colours from CSS vars `--c-office/home/absence/travel/line`, validated with the dataviz palette checker; keep that order/values), `/report/[month]` (printable time sheet, print CSS hides the app chrome), `/absences` (vacation account, range entry with dry-run preview, year calendar), `/settings` (how Pendel calculates: region, employments, work model, places, integrations, adjustments), `/account` (opened via the avatar in the header: name, language, password, 2FA, signed-in devices, logout), `/admin` (mobile: button on `/account`), public `/login`, `/setup`, `/invite/[token]`. The root layout gates non-public routes.
- Styling: Tailwind 4 with custom utilities (`card`, `btn-*`, `input`, `label`, `muted`) defined via `@utility` in `routes/layout.css` (Tailwind 4 cannot `@apply` classes from `@layer components`). Brand colors `brand-*`, place colors `home`/`office`/`travel`. Dark mode follows the OS.
- Local cookies: run the backend with `PENDEL_SECURE_COOKIES=false` when testing over plain HTTP on a non-localhost address.

## Backend architecture

- `models.py` – SQLAlchemy models. Timestamps are UTC (`dbtypes.UTCDateTime`, rejects naive datetimes); sessions and commutes belong to the *local* day (user time zone) on which they start. Running entries have `end = None`.
- `calc.py` – pure accounting rules on plain dataclasses, no DB: day target (holidays/vacation/sick are neutral, flex days keep the target), break handling (`manual` vs. `auto` = fixed daily break, longer recorded breaks win; breaks with `deducted = False` are recorded absences that count as work, e.g. customer visits; office gaps up to `office_gap_break_max_minutes` are breaks), ArbZG warnings, commute credit percentage.
- `reports.py` – loads a user's data for a date range and feeds `calc.evaluate_day`; holidays via the `holidays` package (country + subdivision from the user). The flexitime balance is never stored: `balance()` = sum of `BalanceAdjustment` (opening balance, payouts) + daily diffs since the first `WorkModel`.
- `Employment` (`employments.py`): jobs with start/end. Each one starts a fresh flexitime balance (`balance()` counts from the start of the employment covering the day) and vacation account (`VacationAllowance` is per employment + year; `absences.account_employment()` picks the one shown for a year, carry-over only within the same employment). Days between employments or after the last one ended have no target; days before the first one behave as before. `switch()` ends the current job, starts a new one and copies the work model; `delete_with_data()` removes an ended employment with everything recorded in it. Every user has at least one (created with the user; migration created one per existing user from the first work model).
- `WorkModel` rows are versioned by `valid_from`; the newest model not after a day applies to it, so contract changes keep past days correct.
- Absences: `DayEntry` per day (`DayKind`); `models.NEUTRAL_DAY_KINDS` make a day neutral (target 0), `FLEX_DAY` keeps the target, `VACATION_HALF` halves it. `absences.py` books ranges only on workdays (target > 0 and no holiday, via `reports.schedule`, which falls back to the first work model for earlier days), groups entries into periods and computes the yearly `VacationAllowance` account (taken ≤ today, planned after).
- Automation (`automation.py`, `api/integrations.py`): `POST /api/events` (Bearer token) takes `zone_change` (from/to, e.g. HA person states) or `zone_enter`/`zone_leave`; each part is stored as `Event`, de-duplicated (same type/zone/time ±1 s) and processed immediately by a small state machine (leave home → commute to work, enter office → office session, leave/re-enter office → `office_gap` break deducted by threshold, enter home → session ends at office leave + commute home, home without office → commute discarded, gaps < 3 min dropped as GPS jitter). Actions are written into `Event.payload["actions"]` and shown in the UI log. Zones match `Place.zone` or name, case-insensitive, `zone.` prefix ignored. `POST /api/owntracks` accepts OwnTracks HTTP-mode messages (auth `auth.basic_token_user`: HTTP Basic with the API token as password, user name ignored, Bearer also works): only `transition` enter/leave become zone events (region name = zone), everything else (location fixes, lwt, ...) is acknowledged with `[]` and dropped, as are messages older than `MAX_EVENT_AGE`, because OwnTracks retries anything that isn't 200. The UI (`Integrations.svelte`) creates an "OwnTracks" token and hands the settings over as `owntracks:///config?inline=<base64 JSON>` (QR code + link). `ApiToken` stores only token hashes; `python -m pendel.cli create-token` creates one on the server.
- Migrations run with SQLite foreign keys switched off (`db.migration_connection`), because batch migrations rebuild tables and dropping a parent table would otherwise cascade-delete its children; a `foreign_key_check` runs afterwards.
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
