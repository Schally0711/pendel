from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from .conftest import PASSWORD


def iso(dt: datetime) -> str:
    return dt.isoformat()


def ago(minutes: int) -> datetime:
    return datetime.now(UTC) - timedelta(minutes=minutes)


def test_clock_flow(admin):
    office = next(p for p in admin.get("/api/places").json() if p["kind"] == "office")
    assert (
        admin.post("/api/clock/commute/start", json={"direction": "to_work", "at": iso(ago(240))}).status_code
        == 201
    )
    r = admin.post("/api/clock/start", json={"kind": "office", "place_id": office["id"], "at": iso(ago(200))})
    assert r.status_code == 201
    assert admin.post("/api/clock/start", json={"kind": "office"}).status_code == 409

    today = admin.get("/api/today").json()
    assert today["running_commute"] is None  # arriving ended the commute
    assert today["running_session"]["place_id"] == office["id"]

    assert admin.post("/api/clock/break/start", json={"at": iso(ago(100))}).status_code == 201
    assert admin.post("/api/clock/break/start", json={}).status_code == 409
    assert admin.post("/api/clock/break/stop", json={"at": iso(ago(70))}).status_code == 200
    stopped = admin.post("/api/clock/stop", json={"at": iso(ago(20))}).json()
    assert stopped["end"] is not None and len(stopped["breaks"]) == 1

    berlin = ZoneInfo("Europe/Berlin")
    if ago(240).astimezone(berlin).date() != datetime.now(berlin).date():
        pytest.skip("test data would span local midnight")
    day = admin.get("/api/today").json()["day"]
    assert (day["commute"], day["gross"], day["breaks_effective"], day["actual"]) == (40, 180, 30, 150)


def test_future_time_rejected(admin):
    r = admin.post(
        "/api/clock/start", json={"kind": "home", "at": iso(datetime.now(UTC) + timedelta(hours=1))}
    )
    assert r.status_code == 422


def test_naive_datetime_rejected(admin):
    r = admin.post("/api/sessions", json={"kind": "home", "start": "2026-10-01T08:00:00"})
    assert r.status_code == 422


def test_manual_session_and_report(admin):
    s = admin.post(
        "/api/sessions",
        json={"kind": "home", "start": "2026-10-14T08:00:00+02:00", "end": "2026-10-14T17:00:00+02:00"},
    ).json()
    brk = admin.post(
        f"/api/sessions/{s['id']}/breaks",
        json={"start": "2026-10-14T12:00:00+02:00", "end": "2026-10-14T13:00:00+02:00"},
    )
    assert brk.status_code == 201
    outside = admin.post(
        f"/api/sessions/{s['id']}/breaks",
        json={"start": "2026-10-14T18:00:00+02:00", "end": "2026-10-14T18:30:00+02:00"},
    )
    assert outside.status_code == 422

    # Customer visit: the break does not count
    b = brk.json()
    admin.put(f"/api/breaks/{b['id']}", json={"start": b["start"], "end": b["end"], "deducted": False})

    admin.put("/api/days/2026-10-15", json={"kind": "vacation"})
    rep = admin.get("/api/report", params={"from": "2026-10-14", "to": "2026-10-15"}).json()
    wed, thu = rep["days"]
    assert (wed["actual"], wed["diff"], wed["kinds"]) == (540, 60, ["home"])
    assert (thu["target"], thu["entry"]) == (0, "vacation")


def test_holiday_in_report(admin):
    rep = admin.get("/api/report", params={"from": "2026-12-25", "to": "2026-12-25"}).json()
    assert rep["days"][0]["holiday"] == "Erster Weihnachtstag"
    assert rep["days"][0]["target"] == 0


def test_invalid_range(admin):
    assert admin.get("/api/report", params={"from": "2026-10-10", "to": "2026-10-01"}).status_code == 400


def test_users_cannot_see_each_other(admin):
    s = admin.post("/api/sessions", json={"kind": "home", "start": iso(ago(60)), "end": iso(ago(30))}).json()
    token = admin.post("/api/admin/invitations", json={}).json()["token"]

    other = TestClient(admin.app, headers={"X-Requested-With": "pendel"})
    body = {"email": "o@example.org", "password": PASSWORD, "display_name": "O"}
    assert other.post(f"/api/invitations/{token}/accept", json=body).status_code == 201
    assert other.patch(f"/api/sessions/{s['id']}", json={"note": "x"}).status_code == 404
    assert other.delete(f"/api/sessions/{s['id']}").status_code == 404
    admin_place = admin.get("/api/places").json()[0]["id"]
    assert other.post("/api/clock/start", json={"kind": "home", "place_id": admin_place}).status_code == 404


def test_opening_balance(admin):
    admin.post("/api/adjustments", json={"day": "2026-01-01", "minutes": 600, "note": "Startsaldo"})
    assert admin.get("/api/adjustments").json()[0]["minutes"] == 600


def test_work_model_rules(admin):
    (model,) = admin.get("/api/work-models").json()
    assert admin.delete(f"/api/work-models/{model['id']}").status_code == 409
    dup = admin.post("/api/work-models", json={"valid_from": model["valid_from"]})
    assert dup.status_code == 409
    new = admin.post("/api/work-models", json={"valid_from": "2030-01-01", "break_mode": "auto"})
    assert new.status_code == 201


def test_today_actual_seconds_survive_restart(admin):
    """Short sessions must not be rounded away when work is stopped and restarted."""
    now = datetime.now(UTC)
    admin.post("/api/clock/start", json={"kind": "home", "at": iso(now - timedelta(seconds=100))})
    admin.post("/api/clock/stop", json={"at": iso(now - timedelta(seconds=60))})
    admin.post("/api/clock/start", json={"kind": "home"})
    today = admin.get("/api/today").json()
    assert 40 <= today["actual_seconds"] <= 45
    assert today["day"]["actual"] == 1


def test_today_balance_includes_adjustments_booked_today(admin):
    today = admin.get("/api/today").json()
    day = today["day"]["day"]
    assert admin.post("/api/adjustments", json={"day": day, "minutes": 420}).status_code == 201
    after = admin.get("/api/today").json()
    assert after["balance"] == today["balance"] + 420
    assert after["balance_before_today"] == today["balance_before_today"] + 420


def test_isolation_of_every_object_type(admin):
    """A second user gets 404 for every object of the first one, and sees none of them in lists."""
    s = admin.post("/api/sessions", json={"kind": "home", "start": iso(ago(90)), "end": iso(ago(30))}).json()
    brk = admin.post(
        f"/api/sessions/{s['id']}/breaks", json={"start": iso(ago(60)), "end": iso(ago(50))}
    ).json()
    commute = admin.post(
        "/api/commutes", json={"direction": "to_work", "start": iso(ago(120)), "end": iso(ago(95))}
    ).json()
    adj = admin.post("/api/adjustments", json={"day": "2026-10-01", "minutes": 30}).json()
    tok = admin.post("/api/tokens", json={"name": "x"}).json()
    place = admin.get("/api/places").json()[0]
    model = admin.get("/api/work-models").json()[0]
    emp = admin.get("/api/employments").json()[0]
    login = admin.get("/api/me/sessions").json()[0]

    invite = admin.post("/api/admin/invitations", json={}).json()["token"]
    other = TestClient(admin.app, headers={"X-Requested-With": "pendel"})
    body = {"email": "o@example.org", "password": PASSWORD, "display_name": "O"}
    assert other.post(f"/api/invitations/{invite}/accept", json=body).status_code == 201

    attempts = [
        other.patch(f"/api/sessions/{s['id']}", json={"note": "x"}),
        other.post(f"/api/sessions/{s['id']}/breaks", json={"start": iso(ago(40))}),
        other.put(f"/api/breaks/{brk['id']}", json={"start": iso(ago(60)), "end": iso(ago(55))}),
        other.delete(f"/api/breaks/{brk['id']}"),
        other.put(f"/api/commutes/{commute['id']}", json={"direction": "to_work", "start": iso(ago(120))}),
        other.delete(f"/api/commutes/{commute['id']}"),
        other.put(f"/api/adjustments/{adj['id']}", json={"day": "2026-10-01", "minutes": 1}),
        other.delete(f"/api/adjustments/{adj['id']}"),
        other.delete(f"/api/tokens/{tok['id']}"),
        other.put(f"/api/places/{place['id']}", json={"name": "x", "kind": "home"}),
        other.delete(f"/api/places/{place['id']}"),
        other.put(f"/api/work-models/{model['id']}", json=model),
        other.delete(f"/api/work-models/{model['id']}"),
        other.put(f"/api/employments/{emp['id']}", json={"start": emp["start"]}),
        other.delete(f"/api/employments/{emp['id']}"),
        other.delete(f"/api/me/sessions/{login['id']}"),
        other.get("/api/admin/users"),
    ]
    assert [r.status_code for r in attempts] == [404] * 16 + [403]

    day = ago(0).date()
    rng = {"from": str(day - timedelta(days=2)), "to": str(day + timedelta(days=1))}
    assert other.get("/api/sessions", params=rng).json() == []
    assert other.get("/api/commutes", params=rng).json() == []
    assert other.get("/api/adjustments").json() == []
    assert [t["name"] for t in other.get("/api/tokens").json()] == []
    assert {p["id"] for p in other.get("/api/places").json()}.isdisjoint({place["id"]})
    assert len(other.get("/api/me/sessions").json()) == 1
    # and the first user's data is untouched
    assert len(admin.get("/api/sessions", params=rng).json()[0]["breaks"]) == 1
