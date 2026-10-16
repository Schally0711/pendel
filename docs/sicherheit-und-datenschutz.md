# Sicherheit & Datenschutz

## Was Pendel speichert

Alles liegt in der Datenbank auf **deinem** Server. Pendel sendet nichts an Dritte, hat keine Telemetrie,
lädt keine externen Skripte oder Schriften und braucht keinen Internetzugang (außer du stellst es selbst ins Netz).

| Daten | Wozu |
|---|---|
| Name, E-Mail, Passwort-Hash, Sprache, Zeitzone, Bundesland | Anmeldung, Darstellung, Feiertage |
| Arbeitssitzungen, Pausen, Arbeitswege, Abwesenheiten, Korrekturen | die eigentliche Zeiterfassung |
| Orte mit Name, Art, Entfernung, Zonenname | Zuordnung von Ortsmeldungen, Entfernungspauschale |
| Ortsmeldungen der Automatik (Zeitpunkt, Zone, betreten/verlassen, ausgelöste Aktion) | Nachvollziehbarkeit im Tageseditor |
| Angemeldete Geräte (Browser-Kennung, Anmelde- und letzte Aktivitätszeit) | Geräteübersicht, Abmelden |
| API-Tokens (nur als Hash), Einladungen | Integrationen, Registrierung |

**Keine Standortdaten:** Pendel speichert keine Koordinaten. OwnTracks schickt zwar Standortpunkte mit,
die werden aber sofort verworfen; gespeichert wird nur „Region X betreten/verlassen“.

Jede Person sieht nur ihre eigenen Daten. Admins können Personen einladen und löschen, aber keine Zeiten anderer
einsehen. Beim Löschen einer Person werden alle ihre Daten gelöscht.

**Auskunft und Löschung:** Unter *Konto → Deine Daten* kann jede Person alles, was Pendel über sie speichert, als
JSON herunterladen (ohne Passwort-Hash und Tokens) und ihr Konto selbst löschen. Ausnahme: Der letzte Admin kann sich
nicht löschen, solange es noch andere Konten gibt – vorher eine andere Person zum Admin machen.

Die **Instanz-Sicherung** in der Verwaltung enthält dagegen die komplette Datenbank aller Personen, inklusive
Passwort-Hashes und Token-Hashes. Nur Admins können sie herunterladen.

> Wer Pendel für andere betreibt (Familie, Freunde, Team), verarbeitet deren personenbezogene Daten. Je nach
> Situation gelten dafür die Regeln der DSGVO – das ist Sache der Person, die die Instanz betreibt.

## Anmeldung

- **Passwörter** werden mit Argon2id gehasht (aktuelle Empfehlung, speicherintensiv). Mindestlänge 10 Zeichen.
- **Sitzungen** sind zufällige 256-Bit-Tokens; in der Datenbank steht nur ihr Hash. Das Cookie ist `HttpOnly`,
  `SameSite=Lax` und bei HTTPS `Secure`, gültig 30 Tage. Schreibende Anfragen brauchen zusätzlich einen
  eigenen Header (Schutz gegen CSRF).
- **Begrenzung von Anmeldeversuchen:** 10 Versuche pro IP-Adresse in 15 Minuten und 20 Fehlversuche pro Konto
  in einer Stunde – auch wenn sie von vielen Adressen kommen.
- **Zwei-Faktor-Anmeldung (optional):** unter *Konto → Sicherheit* mit einer Authenticator-App (TOTP) einrichten.
  Dazu gibt es 10 Wiederherstellungscodes, die je einmal funktionieren. Admins können die Zwei-Faktor-Anmeldung
  einer Person zurücksetzen, wenn Handy und Codes verloren sind.
- **Geräte:** unter *Konto → Angemeldete Geräte* siehst du alle Anmeldungen und kannst einzelne oder alle anderen
  abmelden. Eine Passwortänderung und das Einschalten der Zwei-Faktor-Anmeldung melden alle anderen Geräte ab.
- **Erste Einrichtung** nur mit dem Einrichtungscode aus dem Server-Log, damit niemand eine frische Instanz übernimmt.
- **Keine offene Registrierung:** neue Konten nur über Einladungslinks (einmalig, befristet).
- **Passwort vergessen:** Ein Admin erzeugt einen Link zum Zurücksetzen (24 Stunden, einmalig). Danach ist die Person
  überall abgemeldet; eine eingerichtete Zwei-Faktor-Anmeldung bleibt bestehen.
- **API-Tokens** gelten für Integrationen; sie umgehen die Zwei-Faktor-Anmeldung. Gib sie nur Geräten und
  Diensten, denen du vertraust, und widerrufe sie, wenn du sie nicht mehr brauchst.

Weitere Schutzmaßnahmen: Content Security Policy (keine fremden Skripte), `X-Frame-Options: DENY`,
`nosniff`, keine Zwischenspeicherung von API-Antworten, Größenlimit für Anfragen, Container läuft ohne root.

## Empfehlungen für den Betrieb

- Von außen nur über **HTTPS** erreichbar machen (Reverse Proxy oder Tunnel), nie den Port 8000 direkt ins Internet.
- `PENDEL_FORWARDED_ALLOW_IPS` auf die Adresse des Proxys setzen, damit die Begrenzung der Anmeldeversuche die
  echte IP sieht.
- Zwei-Faktor-Anmeldung zumindest für Admin-Konten einschalten.
- Regelmäßig sichern (siehe [Update & Backup](update-und-backup.md)) und Updates einspielen.

## Sicherheitslücke gefunden?

Bitte nicht als öffentliches Issue melden, sondern wie in [SECURITY.md](../SECURITY.md) beschrieben.
