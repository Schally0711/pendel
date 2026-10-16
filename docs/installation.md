# Installation

Pendel besteht aus einem einzigen Dienst (Web-App + API) und speichert alles in einer SQLite-Datenbank.
Empfohlen ist der Betrieb als Docker-Container; ohne Docker geht es auf Debian/Ubuntu mit dem Installationspaket.

- [Docker Compose](#docker-compose) (empfohlen)
- [Erster Start: Einrichtungscode](#erster-start-einrichtungscode)
- [Zugriff von außen: Reverse Proxy und Tunnel](#zugriff-von-außen-reverse-proxy-und-tunnel)
- [Ohne Docker (Debian/Ubuntu, LXC)](#ohne-docker-debianubuntu-lxc)
- [Einstellungen (Umgebungsvariablen)](#einstellungen-umgebungsvariablen)
- [App auf dem Handy installieren](#app-auf-dem-handy-installieren)

## Docker Compose

Voraussetzung: Docker mit Compose-Plugin (oder Podman). Das Image gibt es für `amd64` und `arm64` (z. B. Raspberry Pi 4/5).

```yaml
# compose.yaml
services:
  pendel:
    image: ghcr.io/schally0711/pendel:0.9
    container_name: pendel
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data
    environment:
      TZ: Europe/Berlin
```

```bash
docker compose up -d
```

- Die Daten liegen in `./data` neben der `compose.yaml` (Datenbank `pendel.db`, Sicherungen in `backups/`).
- Image-Tags: `0.9` bekommt alle Fehlerbehebungen der Version 0.9 (empfohlen), `0.9.0` bleibt fest, `latest` folgt
  immer der neuesten Version.
- Der Container startet als root, passt bei Bedarf die Rechte von `/data` an und läuft dann als Benutzer `1000:1000`.
  Andere IDs über `PUID`/`PGID`; mit `--user` bzw. rootless Podman startet er direkt als dieser Benutzer.

Ohne Compose:

```bash
docker run -d --name pendel --restart unless-stopped -p 8000:8000 -v ./data:/data -e TZ=Europe/Berlin \
  ghcr.io/schally0711/pendel:0.9
```

## Erster Start: Einrichtungscode

Solange noch kein Konto existiert, schreibt Pendel beim Start einen einmaligen **Einrichtungscode** ins Log:

```bash
docker logs pendel
#   Pendel is not set up yet. Open it in the browser and enter this setup code: 3F9A-12CD-77E0
```

Öffne `http://<server>:8000`, gib den Code ein und lege das erste Konto an – es wird Admin. Ohne den Code kann
niemand eine frisch gestartete Instanz übernehmen. Der Code ändert sich bei jedem Neustart, bis das Konto angelegt ist.
Für automatisierte Installationen kannst du ihn mit `PENDEL_SETUP_TOKEN` selbst festlegen.

Danach:

1. **Einstellungen → Region & Zeitzone:** Bundesland (für die Feiertage) prüfen.
2. **Einstellungen → Arbeitszeitmodell:** Soll pro Wochentag, Gleitzeit, Pausenregel und „gültig ab“ einstellen.
3. **Einstellungen → Arbeitsverhältnisse:** Arbeitgeber und Eintrittsdatum eintragen (optional).
4. **Verwaltung:** Einladungslinks für weitere Personen erstellen. Eine offene Registrierung gibt es nicht.

Mehr zur Bedienung in [bedienung.md](bedienung.md).

## Zugriff von außen: Reverse Proxy und Tunnel

Pendel selbst spricht nur HTTP. Für den Zugriff übers Internet gehört es hinter einen Reverse Proxy mit HTTPS
(Nginx Proxy Manager, Caddy, Traefik, nginx) oder einen Tunnel (Cloudflare Tunnel, Tailscale Funnel …).

1. Proxy/Tunnel auf `http://<pendel-host>:8000` zeigen lassen.
2. **`PENDEL_FORWARDED_ALLOW_IPS`** auf die Adresse(n) des Proxys bzw. von `cloudflared` setzen (kommagetrennt,
   CIDR erlaubt, z. B. `172.18.0.0/16` für ein Docker-Netz). Nur dann sieht Pendel die echte Client-IP
   (wichtig für die Begrenzung von Anmeldeversuchen) und erkennt HTTPS (für das `Secure`-Cookie).
3. Die externe Adresse unter **Verwaltung → Instanz → Öffentliche Adresse** eintragen (oder `PENDEL_PUBLIC_URL`).
   Sie wird für Einladungslinks, das Kalender-Abo und die Einrichtung der Integrationen verwendet.

Beispiel Caddy (gleicher Host, Compose-Netz):

```
pendel.example.com {
    reverse_proxy pendel:8000
}
```

Beispiel nginx:

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

**Cloudflare Access:** Browser können sich über Access anmelden, Home Assistant, OwnTracks und Kalender-Apps
aber nicht. Wer Access vor Pendel schaltet, braucht eine *Bypass*-Regel für `/api/*` – die API ist durch Pendels
eigene Anmeldung bzw. API-Tokens geschützt.

## Ohne Docker (Debian/Ubuntu, LXC)

Jede Version gibt es auf der [Release-Seite](https://github.com/Schally0711/pendel/releases) auch als
Installationspaket `pendel-<version>.tar.gz` (Web-App + Python-Paket + Installer). Benötigt wird Python ≥ 3.13
(Debian 13, Ubuntu 25.04 oder neuer).

```bash
# als root
tar -xzf pendel-0.9.0.tar.gz
pendel-0.9.0/install.sh
```

Der Installer legt den Benutzer `pendel` und den systemd-Dienst `pendel` an:

| Pfad | Inhalt |
|---|---|
| `/opt/pendel` | Programm (venv, Web-App) |
| `/var/lib/pendel` | Daten (`pendel.db`, `backups/`) |
| `/etc/pendel/pendel.env` | Einstellungen (bleiben bei Updates erhalten) |

Den Einrichtungscode zeigt der Installer beim ersten Start an (sonst: `journalctl -u pendel | grep "setup code"`).
Ein Update ist dasselbe mit dem neuen Paket: entpacken, `install.sh` ausführen.

Selbst bauen statt herunterladen: `deploy/build-release.sh` (braucht Node 24 und Python ≥ 3.13) erzeugt das Paket in `dist/`.

## Einstellungen (Umgebungsvariablen)

Alle Einstellungen sind optional. Bei Docker im `environment:`-Block, ohne Docker in `/etc/pendel/pendel.env`
(danach `systemctl restart pendel`).

| Variable | Standard | Bedeutung |
|---|---|---|
| `TZ` | `Europe/Berlin` | Zeitzone des Containers (nur für Logs; jede Person stellt ihre Zeitzone selbst ein) |
| `PENDEL_PUBLIC_URL` | – | Externe Adresse, z. B. `https://pendel.example.com` (in der Verwaltung überschreibbar) |
| `PENDEL_FORWARDED_ALLOW_IPS` | `127.0.0.1` | Vertrauenswürdige Proxys, deren `X-Forwarded-*`-Header gelten |
| `PENDEL_SECURE_COOKIES` | automatisch | `true`/`false` erzwingt das `Secure`-Flag des Sitzungs-Cookies; automatisch = bei HTTPS-Anfragen |
| `PENDEL_SETUP_TOKEN` | zufällig | Eigener Einrichtungscode für das erste Konto |
| `PENDEL_PORT` | `8000` | Port im Container bzw. des Dienstes |
| `PENDEL_DATA_DIR` | `/data` (Docker) | Datenverzeichnis |
| `PENDEL_DATABASE_URL` | – | Andere Datenbank-URL (SQLAlchemy); getestet ist nur SQLite |
| `PUID` / `PGID` | `1000` | Nur Docker: Benutzer, dem `/data` gehört und unter dem Pendel läuft |

## App auf dem Handy installieren

Pendel ist eine Progressive Web App:

- **Android (Chrome):** Pendel öffnen → Menü → *App installieren*. Langes Drücken auf das Icon zeigt Schnellaktionen
  (Homeoffice starten, Im Büro starten, Feierabend).
- **iOS (Safari):** Teilen → *Zum Home-Bildschirm*.

Die App braucht eine HTTPS-Adresse (oder `localhost`), damit sie sich installieren lässt.
