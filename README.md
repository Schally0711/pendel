# Pendel

Self-hosted work time tracking for people who split their week between **home office** and **office** – including automatic **commute tracking**.

> 🚧 Early development – not usable yet.

## Planned features

- Start/stop/break tracking with a mobile-friendly PWA
- Configurable work time models (weekly hours, flexitime) and public holidays per German state
- Flexitime balance (overtime / undertime), vacation and sick days
- Commute tracking: automatic via Home Assistant zones, Android (Tasker, OwnTracks) or any webhook
- Statistics and charts, CSV/PDF export, tax overview (commuter allowance, home office allowance)
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

## Container

```bash
podman build -t pendel -f Containerfile .
podman run -p 8000:8000 -v pendel-data:/data pendel
```

Configuration via environment variables with prefix `PENDEL_` (see `backend/pendel/config.py`).
