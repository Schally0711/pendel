# Changelog

Alle nennenswerten Änderungen pro Version. Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [0.9.0] – Beta

Erste öffentliche Version.

### Funktionen

- Stempeln für Homeoffice, Büro, Pausen und Arbeitsweg als installierbare Web-App (PWA), Schnellaktionen am App-Icon
- Versionierte Arbeitszeitmodelle mit Soll pro Wochentag, Pausenregel (manuell oder fester Abzug),
  Prüfung von Pausen und Höchstarbeitszeit nach ArbZG, Anrechnung des Arbeitswegs
- Gleitzeitkonto mit Startsaldo und Korrekturen; Arbeitsverhältnisse mit eigenem Konto und Jobwechsel-Assistent
- Abwesenheiten (Urlaub, halber Urlaubstag, krank, Kind krank, Gleittag, Freistellung, Sonderurlaub, Fortbildung,
  Elternzeit, unbezahlter Urlaub, manueller Feiertag), Urlaubskonto mit Übertrag, Jahreskalender
- Feiertage je Bundesland
- Verlauf mit Tageseditor, Statistik, druckbarer Monatsbericht, CSV-Export, Steuerübersicht, iCal-Abo
- Automatische Erfassung über Home Assistant (eigene Integration), OwnTracks und beliebige HTTP-Automationen
- Mehrere Personen per Einladung, Zwei-Faktor-Anmeldung mit Wiederherstellungscodes, Geräteübersicht
- Deutsch und Englisch, heller und dunkler Modus

### Betrieb

- Container-Image für amd64 und arm64, Installationspaket für Debian/Ubuntu ohne Docker
- Einrichtungscode für das erste Konto, automatische Datenbanksicherung vor jeder Migration, `pendel.cli backup`
