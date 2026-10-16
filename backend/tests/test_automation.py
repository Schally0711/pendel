"""Zone events → sessions, commutes and office breaks (Wednesday 14 Oct 2026, Europe/Berlin = UTC+2)."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

DAY = "2026-10-14"


def at(hhmm: str, day: str = DAY) -> str:
    return f"{day}T{hhmm}:00+02:00"


@pytest.fixture
def ha(admin, monkeypatch):
    """Client authenticated only by an API token, like Home Assistant."""
    monkeypatch.setattr("pendel.api.integrations.MAX_EVENT_AGE", timedelta(days=3650))
    (model,) = admin.get("/api/work-models").json()
    admin.put(f"/api/work-models/{model['id']}", json={**model, "valid_from": "2026-01-01"})
    office = next(p for p in admin.get("/api/places").json() if p["kind"] == "office")
    admin.put(f"/api/places/{office['id']}", json={**office, "zone": "Arbeit"})
    token = admin.post("/api/tokens", json={"name": "Home Assistant"}).json()["token"]
    return TestClient(admin.app, headers={"Authorization": f"Bearer {token}"})


def move(ha, hhmm, frm, to, day=DAY):
    r = ha.post("/api/events", json={"type": "zone_change", "from": frm, "to": to, "at": at(hhmm, day)})
    assert r.status_code == 200, r.text
    return [a for e in r.json()["events"] for a in e["payload"]["actions"]]


def day_records(admin, day=DAY):
    params = {"from": day, "to": day}
    return admin.get("/api/sessions", params=params).json(), admin.get("/api/commutes", params=params).json()


def hm(iso: str) -> str:
    return iso[11:16]  # UTC


def test_office_day(admin, ha):
    assert move(ha, "07:20", "home", "not_home") == ["commute_to_work_started"]
    assert move(ha, "08:00", "not_home", "Arbeit") == ["commute_to_work_ended", "office_session_started"]
    # lunch outside: 40 min → break
    assert move(ha, "12:00", "Arbeit", "not_home") == ["office_gap_started"]
    assert move(ha, "12:40", "not_home", "Arbeit") == ["gap_closed_break"]
    # customer visit: 2 h → work
    move(ha, "13:30", "Arbeit", "not_home")
    assert move(ha, "15:30", "not_home", "Arbeit") == ["gap_closed_work"]
    # going home
    assert move(ha, "16:45", "Arbeit", "not_home") == ["office_gap_started"]
    assert move(ha, "17:25", "not_home", "home") == ["office_session_ended", "commute_from_work_recorded"]

    (s,), commutes = day_records(admin)
    assert s["source"] == "automatic" and (hm(s["start"]), hm(s["end"])) == ("06:00", "14:45")
    assert [(b["kind"], b["deducted"]) for b in s["breaks"]] == [("office_gap", True), ("office_gap", False)]
    assert [(c["direction"], hm(c["start"]), hm(c["end"])) for c in commutes] == [
        ("to_work", "05:20", "06:00"),
        ("from_work", "14:45", "15:25"),
    ]
    rep = admin.get("/api/report", params={"from": DAY, "to": DAY}).json()["days"][0]
    # 8:00–16:45 = 525 min − 40 min break
    assert (rep["actual"], rep["commute"], rep["kinds"]) == (485, 80, ["office"])


def test_private_trip_is_discarded(admin, ha):
    move(ha, "07:00", "home", "not_home")
    assert move(ha, "07:30", "not_home", "home") == ["commute_to_work_discarded"]
    assert day_records(admin) == ([], [])


def test_gps_jitter_at_office(admin, ha):
    move(ha, "08:00", "not_home", "Arbeit")
    move(ha, "10:00", "Arbeit", "not_home")
    assert move(ha, "10:01", "not_home", "Arbeit") == ["gap_dropped_jitter"]
    (s,), _ = day_records(admin)
    assert s["breaks"] == []


def test_no_commute_on_weekend_or_vacation(admin, ha):
    assert move(ha, "09:00", "home", "not_home", day="2026-10-11") == ["ignored_no_workday"]  # Sunday
    admin.put("/api/days/2026-10-13", json={"kind": "vacation"})
    assert move(ha, "09:00", "home", "not_home", day="2026-10-13") == ["ignored_no_workday"]


def test_home_office_morning_then_office(admin, ha):
    home = next(p for p in admin.get("/api/places").json() if p["kind"] == "home")
    admin.post("/api/sessions", json={"kind": "home", "place_id": home["id"], "start": at("07:00")})
    assert move(ha, "10:00", "home", "not_home") == ["home_session_ended", "commute_to_work_started"]
    move(ha, "10:30", "not_home", "Arbeit")
    sessions, commutes = day_records(admin)
    assert [(s["kind"], hm(s["start"]), s["end"] and hm(s["end"])) for s in sessions] == [
        ("home", "05:00", "08:00"),
        ("office", "08:30", None),
    ]
    assert len(commutes) == 1


def test_evening_trip_after_office_starts_no_commute(admin, ha):
    move(ha, "08:00", "not_home", "Arbeit")
    move(ha, "16:00", "Arbeit", "not_home")
    move(ha, "16:30", "not_home", "home")
    assert move(ha, "19:00", "home", "not_home") == ["no_change"]


def test_missed_leave_event_estimates_end(admin, ha):
    move(ha, "08:00", "not_home", "Arbeit")
    assert move(ha, "17:00", "not_home", "home") == ["office_session_ended"]
    (s,), _ = day_records(admin)
    assert hm(s["end"]) == "15:00" and "[end_estimated]" in s["note"]


def test_unknown_zone_and_duplicates(admin, ha):
    assert move(ha, "08:00", "not_home", "Fitnessstudio") == ["ignored_unknown_zone"]
    move(ha, "09:00", "not_home", "zone.arbeit")
    r = ha.post("/api/events", json={"type": "zone_enter", "zone": "zone.arbeit", "at": at("09:00")})
    assert r.json()["events"] == []  # same event again (webhook retry)
    events = admin.get("/api/events", params={"from": DAY, "to": DAY}).json()
    assert [(e["type"], e["zone"]) for e in events] == [
        ("zone_enter", "Fitnessstudio"),
        ("zone_enter", "zone.arbeit"),
    ]


def test_event_validation(admin, ha, monkeypatch):
    assert ha.post("/api/events", json={"type": "zone_enter"}).status_code == 422
    assert ha.post("/api/events", json={"type": "teleport", "zone": "home"}).status_code == 422
    monkeypatch.setattr("pendel.api.integrations.MAX_EVENT_AGE", timedelta(days=7))
    old = ha.post("/api/events", json={"type": "zone_enter", "zone": "home", "at": at("08:00", "2020-01-01")})
    assert old.status_code == 422


def test_tokens(admin, ha):
    tokens = admin.get("/api/tokens").json()
    assert [t["name"] for t in tokens] == ["Home Assistant"] and tokens[0]["last_used_at"] is None
    move(ha, "08:00", "not_home", "Arbeit")
    assert admin.get("/api/tokens").json()[0]["last_used_at"] is not None
    admin.delete(f"/api/tokens/{tokens[0]['id']}")
    assert ha.post("/api/events", json={"type": "zone_enter", "zone": "home"}).status_code == 401
    # token works without the CSRF header, cookie writes do not
    assert ha.headers.get("X-Requested-With") is None


def test_cli_create_token(admin, tmp_path, capsys):
    from pendel.cli import main

    out = tmp_path / "t.token"
    assert main(["create-token", "admin@example.org", "CLI", "--out", str(out)]) == 0
    token = out.read_text().strip()
    assert oct(out.stat().st_mode)[-3:] == "600"
    c = TestClient(admin.app, headers={"Authorization": f"Bearer {token}"})
    assert c.get("/api/me").json()["email"] == "admin@example.org"
    assert main(["create-token", "nobody@example.org", "x"]) == 1
