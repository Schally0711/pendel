from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from pendel.stats import commuter_allowance, home_office_rate

from .test_automation import at, move


@pytest.fixture
def week(admin, monkeypatch):
    """Mon 12 – Fri 16 Oct 2026: office Mon/Wed (automatic, with commutes), home Tue, vacation Thu."""
    monkeypatch.setattr("pendel.api.integrations.MAX_EVENT_AGE", timedelta(days=3650))
    (model,) = admin.get("/api/work-models").json()
    admin.put(f"/api/work-models/{model['id']}", json={**model, "valid_from": "2026-10-12"})
    places = admin.get("/api/places").json()
    office = next(p for p in places if p["kind"] == "office")
    home = next(p for p in places if p["kind"] == "home")
    admin.put(f"/api/places/{office['id']}", json={**office, "zone": "Arbeit", "distance_km": 28})
    token = admin.post("/api/tokens", json={"name": "HA"}).json()["token"]
    ha = TestClient(admin.app, headers={"Authorization": f"Bearer {token}"})
    for day, leave, arrive, go, home_at in (
        ("2026-10-12", "07:20", "08:00", "16:30", "17:10"),
        ("2026-10-14", "07:30", "08:00", "17:00", "17:45"),
    ):
        move(ha, leave, "home", "not_home", day)
        move(ha, arrive, "not_home", "Arbeit", day)
        move(ha, go, "Arbeit", "not_home", day)
        move(ha, home_at, "not_home", "home", day)
    s = admin.post(
        "/api/sessions",
        json={
            "kind": "home",
            "place_id": home["id"],
            "start": at("08:30", "2026-10-13"),
            "end": at("17:00", "2026-10-13"),
        },
    ).json()
    admin.post(
        f"/api/sessions/{s['id']}/breaks",
        json={"start": at("12:00", "2026-10-13"), "end": at("12:30", "2026-10-13")},
    )
    admin.put("/api/days/2026-10-15", json={"kind": "vacation"})
    return admin


def test_stats(week):
    r = week.get("/api/stats", params={"from": "2026-10-12", "to": "2026-10-16"}).json()
    assert r["group"] == "week"
    days = {d["day"]: d for d in r["days"]}
    mon = days["2026-10-12"]
    assert (mon["place"], mon["start"], mon["end"], mon["commute_to"], mon["commute_from"]) == (
        "office",
        480,
        990,
        40,
        40,
    )
    assert days["2026-10-13"]["place"] == "home" and days["2026-10-13"]["actual"] == 480
    assert days["2026-10-15"]["entry"] == "vacation" and days["2026-10-15"]["target"] == 0
    # balance runs day by day: Mon +30, Tue 0, Wed +60, Thu 0, Fri -480 (nothing recorded) –
    # unless Friday is today: an unfinished day only counts what has been worked
    from datetime import datetime
    from zoneinfo import ZoneInfo

    friday_is_today = datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat() == "2026-10-16"
    assert [d["balance"] for d in r["days"]] == [30, 30, 90, 90, 90 if friday_is_today else -390]
    s = r["summary"]
    assert (s["office_days"], s["home_days"], s["absence_days"]) == (2, 1, {"vacation": 1})
    assert s["avg_commute_to"] == 35 and s["avg_commute_from"] == 42.5
    assert s["commute_by_weekday"][0] == 80 and s["commute_by_weekday"][1] is None
    assert s["longest_day"] == "2026-10-14" and s["worked_days"] == 3
    (p,) = r["periods"]
    assert (p["key"], p["office_days"], p["home_days"], p["absence_days"]) == ("2026-W42", 2, 1, 1)


def test_stats_month_grouping(week):
    r = week.get("/api/stats", params={"from": "2026-01-01", "to": "2026-10-16"}).json()
    assert r["group"] == "month" and r["periods"][-1]["key"] == "2026-10"


def test_tax(week):
    t = week.get("/api/tax/2026").json()
    assert (t["office_days"], t["home_office_days"]) == (2, 1)
    assert t["offices"][0]["distance_km"] == 28 and t["commuter_total"] == round(2 * 28 * 0.38, 2)
    assert t["home_office_total"] == 6.0 and not t["missing_distance"]


def test_tax_rates():
    assert commuter_allowance(28, 2025) == pytest.approx(20 * 0.30 + 8 * 0.38)
    assert commuter_allowance(28, 2026) == pytest.approx(28 * 0.38)
    assert home_office_rate(2024) == (6.0, 210)


def test_csv_export(week):
    r = week.get("/api/export.csv", params={"from": "2026-10-12", "to": "2026-10-16"})
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.content.decode("utf-8-sig").splitlines()
    assert lines[0].startswith("Datum;Wochentag;Tagesart;Ort;Beginn;Ende")
    # 8.5 h without a break → ArbZG warning
    assert lines[1] == "12.10.2026;Mo;;Büro;8:00;16:30;;1:20;8:00;8:30;+0:30;+0:30;Warnung Arbeitszeitgesetz"
    assert lines[4].split(";")[2] == "Urlaub"


def test_calendar_feed(week):
    week.post(
        "/api/absences",
        json={"start": "2026-12-21", "end": "2026-12-31", "kind": "vacation", "note": "Weihnachten"},
    )
    assert week.get("/api/calendar").json() == {
        "active": False,
        "created_at": None,
        "last_used_at": None,
        "url_path": None,
    }
    created = week.post("/api/calendar/token").json()
    url = created["url_path"]
    anon = TestClient(week.app)
    ics = anon.get(url)
    assert ics.status_code == 200 and ics.headers["content-type"].startswith("text/calendar")
    body = ics.text
    assert "SUMMARY:Urlaub – Weihnachten" in body
    assert "DTSTART;VALUE=DATE:20261221" in body and "DTEND;VALUE=DATE:20270101" in body
    assert "SUMMARY:Erster Weihnachtstag" in body
    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))
    # the calendar token cannot be used for the API
    token = url.split("token=")[1]
    assert (
        TestClient(week.app, headers={"Authorization": f"Bearer {token}"}).get("/api/me").status_code == 401
    )
    # a new link revokes the old one
    week.post("/api/calendar/token")
    assert anon.get(url).status_code == 404
    week.delete("/api/calendar/token")
    assert week.get("/api/calendar").json()["active"] is False


def test_today_counts_only_worked_time(admin):
    from datetime import UTC, datetime, timedelta
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()
    (model,) = admin.get("/api/work-models").json()
    admin.put(
        f"/api/work-models/{model['id']}",
        json={**model, "valid_from": today, "target_sat": 480, "target_sun": 480},
    )
    start = datetime.now(UTC) - timedelta(hours=2)
    admin.post(
        "/api/sessions",
        json={"kind": "home", "start": start.isoformat(), "end": (start + timedelta(hours=1)).isoformat()},
    )
    (d,) = admin.get("/api/stats", params={"from": today, "to": today}).json()["days"]
    assert (d["target"], d["diff"], d["balance"]) == (60, 0, 0)
