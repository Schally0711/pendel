# Update & Backup

Alle Daten stecken in **einer Datei**: `pendel.db` im Datenverzeichnis (Docker: `./data`, ohne Docker:
`/var/lib/pendel`). Das Programm selbst enthält keine Daten – ein Update tauscht nur das Programm aus.

## Update

**Docker Compose:**

```bash
docker compose pull
docker compose up -d
```

**Ohne Docker:** neues Installationspaket von der [Release-Seite](https://github.com/Schally0711/pendel/releases)
entpacken und `install.sh` ausführen.

Beim Start bringt Pendel die Datenbank selbst auf den Stand der neuen Version (Migration). **Vorher legt es
automatisch eine Sicherung an**, sofern sich an der Datenbank etwas ändert:

```
data/backups/pendel-before-0.9.1-20261101-071502.db
```

Die letzten fünf dieser automatischen Sicherungen bleiben erhalten. Was sich in einer Version ändert, steht im
[CHANGELOG](../CHANGELOG.md).

**Welches Image-Tag?** `0.9` bekommt nur Fehlerbehebungen der Version 0.9 und ist die sichere Wahl.
`latest` nimmt auch neue Versionen mit, die größere Änderungen bringen können.

## Sicherung über die Oberfläche

Unter **Verwaltung → Sicherung der Instanz** lädt ein Admin die komplette Datenbank herunter
(`pendel-backup-<datum>.db`) – mit allen Personen, Zeiten, Einstellungen, Passwörtern (als Hash) und Tokens.
Damit lässt sich Pendel umziehen oder neu aufsetzen:

- **Neue Instanz:** Auf der Einrichtungsseite den Einrichtungscode eingeben und *Stattdessen eine Sicherung
  einspielen* wählen. Danach meldet sich jeder mit seinem bisherigen Konto an; auch Home Assistant und andere
  Integrationen funktionieren mit ihren Tokens weiter (Adresse ggf. anpassen).
- **Bestehende Instanz:** *Sicherung einspielen* in der Verwaltung ersetzt **alle** Daten (Bestätigung mit Passwort).
  Die bisherige Datenbank wird vorher als `backups/pendel-before-restore-…db` gesichert.

Sicherungen älterer Versionen werden beim Einspielen automatisch auf die aktuelle Version gebracht; Sicherungen
einer neueren Version lehnt Pendel ab. Die Datei enthält alle Daten – bewahre sie entsprechend sicher auf.

## Sicherung auf dem Server

Eine Kopie von `pendel.db` mit `cp`, während Pendel läuft, ist **nicht zuverlässig**: SQLite schreibt neue Daten
zunächst in eine Nebendatei (`pendel.db-wal`). Nimm stattdessen den eingebauten Befehl – er erzeugt eine
vollständige, konsistente Kopie im laufenden Betrieb:

```bash
# Docker
docker exec -u 1000 pendel python -m pendel.cli backup
# → /data/backups/pendel-manual-20261101-200000.db

# ohne Docker
runuser -u pendel -- env $(grep -v '^#' /etc/pendel/pendel.env | xargs) \
  /opt/pendel/venv/bin/python -m pendel.cli backup
```

Mit einem Dateinamen als Argument landet die Kopie dort (`... backup /data/mein-backup.db`).

Für eine regelmäßige Sicherung den Befehl z. B. per Cron nächtlich ausführen und den Ordner `backups/`
(oder das ganze Datenverzeichnis) mit deinem normalen Backup sichern. Alternativ: Pendel kurz stoppen und das
komplette Datenverzeichnis kopieren – im gestoppten Zustand ist die Datei konsistent.

## Wiederherstellen

1. Pendel stoppen: `docker compose stop` (bzw. `systemctl stop pendel`).
2. Die aktuelle Datenbank zur Seite legen und die Sicherung an ihre Stelle kopieren. Die Nebendateien
   `-wal` und `-shm` gehören zur alten Datenbank und müssen weg:

   ```bash
   cd data
   mv pendel.db pendel.db.kaputt
   rm -f pendel.db-wal pendel.db-shm
   cp backups/pendel-before-0.9.1-20261101-071502.db pendel.db
   ```

3. Pendel wieder starten: `docker compose start` (bzw. `systemctl start pendel`).

## Zurück auf eine ältere Version

Eine Migration lässt sich nicht automatisch rückgängig machen. Wenn eine neue Version Probleme macht:

1. In der `compose.yaml` die vorherige Version fest eintragen, z. B. `image: ghcr.io/schally0711/pendel:0.9.0`.
2. Die Sicherung **von vor dem Update** (`backups/pendel-before-<neue Version>-…db`) wie oben wiederherstellen.
3. `docker compose up -d`.

Alles, was zwischen Update und Rückkehr erfasst wurde, ist danach nicht mehr in der Datenbank – trage es bei Bedarf
nach oder melde den Fehler als [Issue](https://github.com/Schally0711/pendel/issues), damit er in der nächsten
Version behoben wird.
