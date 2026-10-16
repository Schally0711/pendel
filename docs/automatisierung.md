# Automatisierung

Pendel kann Arbeitsweg, Bürozeit und Pausen selbst erfassen, wenn dein Handy (oder Home Assistant) meldet,
dass du **Zuhause** oder das **Büro** betrittst bzw. verlässt. Dazu gibt es drei Wege:

- [Home Assistant](#home-assistant) – Integration über HACS, mit Sensoren und Knöpfen
- [OwnTracks](#owntracks) – kostenlose App für Android und iOS, ohne Home Assistant
- [Kurzbefehle, Tasker, MacroDroid & Co.](#kurzbefehle-tasker-macrodroid--co) – alles, was HTTP-Anfragen senden kann

Für Stempeln ohne Standort gibt es die Schnellaktionen am App-Icon (siehe [Bedienung](bedienung.md#heute-stempeln)).

## So erkennt Pendel deinen Tag

Grundlage sind deine **Orte** (Einstellungen → Orte). Eine Ortsmeldung passt zu einem Ort, wenn ihr Name der
**Zone** oder dem **Namen** des Ortes entspricht (Groß-/Kleinschreibung egal, ein `zone.`-Präfix wird ignoriert).

| Ereignis | Ergebnis |
|---|---|
| Zuhause verlassen (Arbeitstag, noch nichts erfasst) | Arbeitsweg zur Arbeit beginnt; eine laufende Homeoffice-Sitzung endet |
| Büro betreten | Arbeitsweg endet, Bürozeit beginnt |
| Büro verlassen und wieder betreten | kurze Abwesenheit (≤ eingestellte *Abwesenheit vom Büro*, Standard 90 min) = Pause, länger = Arbeitszeit (z. B. Kundentermin) |
| Nach dem Büro Zuhause betreten | Bürozeit endet beim Verlassen des Büros, die Zeit bis Zuhause wird Heimweg |
| Zuhause betreten, ohne im Büro gewesen zu sein | der angefangene Arbeitsweg war eine private Fahrt und wird verworfen |

Abwesenheiten unter 3 Minuten gelten als GPS-Zittern und werden ignoriert. Was die Automatik getan hat, steht im
Tageseditor unter *Automatik-Protokoll* – jeder Eintrag lässt sich danach wie ein manueller ändern.

## Home Assistant

Die Integration [pendel-homeassistant](https://github.com/Schally0711/pendel-homeassistant) verbindet sich über die
Oberfläche (kein YAML):

1. In HACS → *Benutzerdefinierte Repositories* `https://github.com/Schally0711/pendel-homeassistant`
   (Typ *Integration*) hinzufügen, **Pendel** installieren und Home Assistant neu starten.
2. *Einstellungen → Geräte & Dienste → Integration hinzufügen → Pendel*: Adresse von Pendel, E-Mail, Passwort
   (und bei Zwei-Faktor-Anmeldung den Code). Home Assistant erstellt sich damit einen eigenen API-Token; das
   Passwort wird nicht gespeichert.
3. Person und Zonen für Zuhause und Büro wählen. Pendel übernimmt die Zonen in die Orte.

Danach meldet Home Assistant Zonenwechsel der Person an Pendel. Die Integration liefert außerdem Sensoren
(Status, heute gearbeitet, Gleitzeitkonto, Woche, Pausen, Arbeitsweg, Resturlaub, nächste Abwesenheit) und Knöpfe
(Homeoffice/Büro starten, Pause, Feierabend) für Dashboards und eigene Automationen.

## OwnTracks

[OwnTracks](https://owntracks.org) meldet das Betreten und Verlassen von Regionen. Pendel nutzt nur diese
Meldungen; normale Standortpunkte verwirft es sofort, Koordinaten werden nicht gespeichert.

1. OwnTracks aus dem Play Store bzw. App Store installieren.
2. **Nur iPhone:** In OwnTracks unter *Einstellungen* den Schalter **„Allow external configuration“** einschalten.
   Ohne ihn lehnt die iOS-App jede Konfiguration per Link ab („URI or file configuration not allowed“).
3. In Pendel unter **Einstellungen → Integrationen → OwnTracks** auf *Zugang für OwnTracks erstellen* tippen und
   den QR-Code mit dem Handy scannen (oder am Handy *In OwnTracks öffnen*). OwnTracks übernimmt Modus, Adresse und
   Zugangsdaten.
4. In OwnTracks unter *Regionen* Regionen mit **genau den Namen deiner Pendel-Orte** anlegen (z. B. „Zuhause“, „Büro“).
   Ein Radius von 100–200 m funktioniert gut.
5. Standortzugriff *Immer erlauben* und OwnTracks von der Akku-Optimierung ausnehmen.

Manuelle Einrichtung: Modus *HTTP*, URL `https://<deine-pendel-adresse>/api/owntracks`, Authentifizierung an,
Benutzer beliebig (z. B. `pendel`), Passwort = ein API-Token aus Pendel.

## Kurzbefehle, Tasker, MacroDroid & Co.

Jede App, die HTTP-Anfragen senden kann, steuert Pendel mit einem **API-Token** (Einstellungen → Integrationen →
*Token erstellen*). Der Token wird nur einmal angezeigt und kann jederzeit widerrufen werden.

```http
POST https://<deine-pendel-adresse>/api/events
Authorization: Bearer <Token>
Content-Type: application/json

{"type": "zone_enter", "zone": "Büro"}
```

| Aktion | Anfrage | Inhalt |
|---|---|---|
| Ort betreten | `POST /api/events` | `{"type": "zone_enter", "zone": "Büro"}` |
| Ort verlassen | `POST /api/events` | `{"type": "zone_leave", "zone": "Zuhause"}` |
| Ortswechsel (z. B. Home-Assistant-Zustände) | `POST /api/events` | `{"type": "zone_change", "from": "home", "to": "not_home"}` |
| Homeoffice starten | `POST /api/clock/start` | `{"kind": "home"}` |
| Im Büro starten | `POST /api/clock/start` | `{"kind": "office"}` |
| Pause starten / beenden | `POST /api/clock/break/start` bzw. `/break/stop` | `{}` |
| Feierabend | `POST /api/clock/stop` | `{}` |

Optional `"at": "2026-10-14T07:18:00+02:00"` mitsenden, wenn die Meldung verzögert ankommt (bis zu 7 Tage zurück).

**iOS-Kurzbefehle:** *Automation → Ankommen* (bzw. *Verlassen*) am Ort wählen, *Sofort ausführen*, Aktion
*Inhalte von URL abrufen*: URL wie oben, Methode *POST*, Header `Authorization` = `Bearer <Token>`, Anfragetext
*JSON* mit `type` und `zone`.

**Tasker / MacroDroid (Android):** Auslöser z. B. *Ort betreten*, *WLAN verbunden* (Büro-WLAN) oder *NFC-Tag*,
Aktion *HTTP Request* bzw. *HTTP-Anfrage* mit den Werten oben.

## API

Alle Funktionen der Oberfläche gibt es auch als API unter `/api`. Die interaktive Dokumentation (OpenAPI) liegt auf
jeder Instanz unter **`/api/docs`**.

- Anmeldung für Skripte: `Authorization: Bearer <API-Token>`.
- Integrationen können sich selbst einen Token holen: `POST /api/auth/token` mit `email`, `password`, `name`
  (und `totp`, wenn die Zwei-Faktor-Anmeldung aktiv ist).
- Auf dem Server: `python -m pendel.cli create-token <email> <name>` (Docker: `docker exec -u 1000 pendel python -m pendel.cli create-token …`).
