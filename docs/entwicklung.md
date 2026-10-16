# Entwicklung

## Aufbau

| Ordner | Inhalt |
|---|---|
| `backend/` | FastAPI + SQLAlchemy 2 + SQLite, Paket `pendel`, Migrationen mit Alembic (laufen beim Start automatisch) |
| `frontend/` | SvelteKit (Svelte 5) als reine SPA, Tailwind CSS 4, Übersetzungen mit Paraglide (`messages/de.json`, `en.json`) |
| `deploy/` | Installationspaket (`build-release.sh`, `install.sh`, systemd-Dienst), Container-Startskript |
| `tools/` | Hilfsskripte, z. B. `screenshots.py` für die Bilder in `docs/images` |
| `Containerfile`, `compose.yaml` | Container-Image und Beispiel |

Code, Kommentare und Commits sind auf Englisch; jeder sichtbare Text der Oberfläche läuft über Paraglide und
braucht einen deutschen und einen englischen Eintrag. Mehr Details zur Architektur stehen in [`CLAUDE.md`](../CLAUDE.md).

## Lokal starten

Voraussetzungen: Python ≥ 3.13, Node.js 24.

```bash
# Backend: http://127.0.0.1:8000, API-Doku unter /api/docs
cd backend
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
PENDEL_SETUP_TOKEN=dev .venv/bin/uvicorn pendel.main:app --reload

# Frontend: http://localhost:5173, leitet /api an das Backend weiter
cd frontend
npm install
npm run dev
```

Der Einrichtungscode ist mit `PENDEL_SETUP_TOKEN=dev` dann `dev`.

## Tests und Prüfungen

```bash
cd backend
.venv/bin/pytest                         # alle Tests (nutzen jeweils eine temporäre Datenbank)
.venv/bin/ruff check . && .venv/bin/ruff format .

cd frontend
npm run check                            # Übersetzungen kompilieren + svelte-check
npm run build
```

Dieselben Prüfungen laufen in GitHub Actions bei jedem Push und Pull Request (`.github/workflows/ci.yml`),
zusätzlich wird das Container-Image gebaut.

## Datenbank ändern

Nach Änderungen an `backend/pendel/models.py` eine Migration erzeugen und **prüfen**:

```bash
cd backend
PENDEL_DATA_DIR=/tmp/x .venv/bin/alembic upgrade head
PENDEL_DATA_DIR=/tmp/x .venv/bin/alembic revision --autogenerate -m "describe the change"
```

SQLite kann viele Änderungen nur durch Neuaufbau der Tabelle; Alembic läuft deshalb im Batch-Modus und mit
abgeschalteten Fremdschlüsseln. Datenmigrationen (z. B. neue Pflichtspalten) gehören von Hand in die erzeugte Datei.

## Screenshots

`tools/screenshots.py` füllt eine leere Instanz mit erfundenen Beispieldaten und erzeugt die Bilder in `docs/images`:

```bash
cd backend
PENDEL_DATA_DIR=/tmp/pendel-demo PENDEL_SETUP_TOKEN=demo PENDEL_STATIC_DIR=../frontend/build \
  .venv/bin/uvicorn pendel.main:app --port 8765 &
python ../tools/screenshots.py http://127.0.0.1:8765 demo   # braucht Playwright
```

## Release

1. Version in `backend/pyproject.toml`, `backend/pendel/__init__.py` und `frontend/package.json` erhöhen,
   `CHANGELOG.md` ergänzen.
2. Tag setzen und pushen: `git tag v0.9.1 && git push --tags`.
3. Der Workflow `release.yml` baut das Image für amd64/arm64 (`ghcr.io/schally0711/pendel:<version>`, `:<major.minor>`,
   `:latest`) und legt ein GitHub-Release mit dem Installationspaket an. Versionen `0.x` werden als Vorabversion markiert.
