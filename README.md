# Pendel

Self-hosted work time tracking for people who split their week between **home office** and **office** – including automatic **commute tracking**.

> 🚧 Early development – not usable yet.

## Planned features

- Start/stop/break tracking with a mobile-friendly PWA
- Configurable work time models (weekly hours, flexitime) and public holidays per German state
- Flexitime balance (overtime / undertime)
- Time off: vacation ranges (weekends/holidays skipped), yearly vacation account with carry-over, sick days, child sick days, flex days, release, training, parental/unpaid leave
- Commute tracking: automatic via Home Assistant zones, Android (Tasker, OwnTracks) or any webhook
- Statistics: flexitime balance over time, hours per week/month vs. target, office/home share, working hours window,
  commute by weekday; printable monthly time sheet (PDF via the browser) and CSV export
- Tax overview per year (German commuter allowance and home office allowance)
- iCal subscription for time off and public holidays
- German and English UI
- Single container with SQLite – easy to host

## Development

Requirements: Python ≥ 3.13, Node.js 24.

```bash
# Backend (http://127.0.0.1:8000, API docs at /api/docs)
cd backend
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/uvicorn pendel.main:app --reload

# Frontend (http://localhost:5173, proxies /api to the backend)
cd frontend
npm install
npm run dev
```

## Installation (Debian/Ubuntu, e.g. a Proxmox LXC)

```bash
deploy/build-release.sh                 # on a build machine with Node 24 + Python ≥ 3.13
# copy dist/pendel-<version>.tar.gz to the server, then as root:
tar -xzf pendel-<version>.tar.gz && pendel-<version>/install.sh
```

Runs as systemd service `pendel` on port 8000; data in `/var/lib/pendel`, settings in `/etc/pendel/pendel.env`.
Put it behind an HTTPS reverse proxy and set `PENDEL_FORWARDED_ALLOW_IPS` to the proxy address.
Re-running `install.sh` with a newer release updates in place; the database is migrated on startup.
On first visit you create the admin account; further people join via invitation links.

Pendel is a PWA: on Android open it in Chrome and choose "Install app".

## Reverse proxy, Cloudflare Tunnel, public address

Pendel can run behind any reverse proxy (nginx, Nginx Proxy Manager, Caddy, Traefik) or a Cloudflare Tunnel:

- Point the proxy/tunnel at `http://<pendel-host>:8000`; HTTPS terminates at the proxy. Keep `PENDEL_SECURE_COOKIES=true`
  (only set it to `false` for plain HTTP without TLS).
- Set `PENDEL_FORWARDED_ALLOW_IPS` in `/etc/pendel/pendel.env` to the address(es) of your proxy/`cloudflared`
  (comma separated) so login rate limiting and logs see the real client IP. Restart with `systemctl restart pendel`.
- Enter the external address under **Admin → Instance → Public address** (or set `PENDEL_PUBLIC_URL`). Pendel uses it for
  invitation links, the calendar subscription (incl. "Subscribe in Google Calendar") and the Home Assistant setup hint.
- **Cloudflare Access:** browsers can log in through Access, but Home Assistant and calendar apps cannot. If you put
  Access in front of Pendel, add a *Bypass* policy for `/api/*` – the API is protected by Pendel's own session/API tokens –
  or at least for `/api/calendar.ics` and `/api/events`.

## Automation (Home Assistant & co.)

**Home Assistant:** use the integration [pendel-homeassistant](https://github.com/Schally0711/pendel-homeassistant) – setup via the UI, no YAML.
Integrations can obtain a token with `POST /api/auth/token` (`email`, `password`, `name`).

For other automations create an API token under *Settings → Integrations* (or on the server: `/opt/pendel/venv/bin/python -m pendel.cli create-token <email> <name>`),
set the zone names of your places (e.g. home = `home`, office = `Work`), then send location events:

```http
POST /api/events
Authorization: Bearer <token>
Content-Type: application/json

{"type": "zone_change", "from": "home", "to": "not_home", "at": "2026-10-14T07:18:00+02:00"}
```

`zone_enter` / `zone_leave` with `"zone": "..."` work as well. Pendel derives commutes, office time and breaks
(absences from the office up to 90 min = break, longer = work).

## Container

```bash
podman build -t pendel -f Containerfile .
podman run -p 8000:8000 -v pendel-data:/data pendel
```

Configuration via environment variables with prefix `PENDEL_` (see `backend/pendel/config.py`).
