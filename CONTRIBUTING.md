# Mitmachen

Danke, dass du Pendel verbessern willst! Fehlerberichte, Ideen und Pull Requests sind willkommen.

## Fehler melden und Ideen

- **Fehler:** [Issue „Fehler melden“](https://github.com/Schally0711/pendel/issues/new?template=bug.yml) – mit Version
  (unten in *Verwaltung* oder `GET /api/health`), Installationsart und Schritten zum Nachstellen.
- **Ideen:** [Issue „Idee / Wunsch“](https://github.com/Schally0711/pendel/issues/new?template=feature.yml) –
  beschreibe vor allem, *welches Problem* du lösen willst.
- **Sicherheitslücken** bitte nie öffentlich, sondern wie in [SECURITY.md](SECURITY.md) beschrieben.
- Fragen zur Home-Assistant-Integration gehören ins Repo [pendel-homeassistant](https://github.com/Schally0711/pendel-homeassistant/issues).

## Pull Requests

1. Für größere Änderungen vorher ein Issue aufmachen, damit wir die Richtung abstimmen.
2. Lokales Setup, Tests und Aufbau stehen in [docs/entwicklung.md](docs/entwicklung.md).
3. Vor dem PR: `pytest` und `ruff check . && ruff format .` im Backend, `npm run check` im Frontend.
4. Code, Kommentare und Commit-Messages auf Englisch; jeder sichtbare Text über Paraglide mit deutschem **und**
   englischem Eintrag (`frontend/messages/*.json`).
5. Neue Funktionen bekommen Tests; ändert sich das Verhalten, bitte auch `docs/` und `CHANGELOG.md` anpassen.

Mit einem Pull Request stellst du deinen Beitrag unter die Lizenz des Projekts ([AGPL-3.0](LICENSE)).

---

**English:** Bug reports, ideas and pull requests are welcome – issues may be written in English or German.
Please open an issue before larger changes, run the tests (`pytest`, `ruff`, `npm run check`), keep code and
commits in English and add both German and English UI texts. Security issues: see [SECURITY.md](SECURITY.md).
