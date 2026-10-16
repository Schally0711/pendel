"""OwnTracks HTTP mode: region transitions become zone events (14 Oct 2026, Europe/Berlin)."""

import base64
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from .test_automation import DAY, day_records, hm


def tst(hhmm: str) -> int:
    return int(datetime.fromisoformat(f"{DAY}T{hhmm}:00+02:00").timestamp())


@pytest.fixture
def token(admin, monkeypatch):
    monkeypatch.setattr("pendel.api.integrations.MAX_EVENT_AGE", timedelta(days=3650))
    (model,) = admin.get("/api/work-models").json()
    admin.put(f"/api/work-models/{model['id']}", json={**model, "valid_from": "2026-01-01"})
    # OwnTracks region names are matched against place names (or zones)
    home = next(p for p in admin.get("/api/places").json() if p["kind"] == "home")
    admin.put(f"/api/places/{home['id']}", json={**home, "zone": None})
    return admin.post("/api/tokens", json={"name": "OwnTracks"}).json()["token"]


def phone(admin, password: str) -> TestClient:
    auth = base64.b64encode(f"yannick:{password}".encode()).decode()
    return TestClient(admin.app, headers={"Authorization": f"Basic {auth}"})


def transition(event: str, region: str, hhmm: str) -> dict:
    return {
        "_type": "transition",
        "event": event,
        "desc": region,
        "tst": tst(hhmm),
        "t": "c",
        "lat": 51.1,
        "lon": 7.1,
    }


def test_office_day_via_owntracks(admin, token):
    p = phone(admin, token)
    for msg in (
        transition("leave", "Zuhause", "07:20"),
        {"_type": "location", "lat": 51.2, "lon": 7.2, "tst": tst("07:40")},  # ignored
        transition("enter", "Büro", "08:00"),
        transition("leave", "Büro", "16:45"),
        transition("enter", "Zuhause", "17:25"),
    ):
        r = p.post("/api/owntracks", json=msg)
        assert (r.status_code, r.json()) == (200, [])

    (s,), commutes = day_records(admin)
    assert (hm(s["start"]), hm(s["end"]), s["kind"]) == ("06:00", "14:45", "office")
    assert [(c["direction"], hm(c["start"]), hm(c["end"])) for c in commutes] == [
        ("to_work", "05:20", "06:00"),
        ("from_work", "14:45", "15:25"),
    ]
    events = admin.get("/api/events", params={"from": DAY, "to": DAY}).json()
    assert len(events) == 4 and all(e["payload"]["source"] == "owntracks" for e in events)
    assert all("lat" not in str(e) for e in events)  # no coordinates stored


def test_owntracks_auth(admin, token):
    raw = TestClient(admin.app)
    # without any Authorization header the CSRF guard answers first
    assert raw.post("/api/owntracks", json=transition("enter", "Büro", "08:00")).status_code == 403
    r = phone(admin, "wrong-token").post("/api/owntracks", json=transition("enter", "Büro", "08:00"))
    assert r.status_code == 401 and r.headers["www-authenticate"].startswith("Basic")
    bearer = TestClient(admin.app, headers={"Authorization": f"Bearer {token}"})
    assert bearer.post("/api/owntracks", json={"_type": "lwt"}).status_code == 200


def test_unusable_messages_are_acknowledged(admin, token, monkeypatch):
    monkeypatch.setattr("pendel.api.integrations.MAX_EVENT_AGE", timedelta(days=7))
    p = phone(admin, token)
    for body in (
        transition("enter", "Büro", "08:00"),  # older than 7 days
        {"_type": "transition", "event": "dance", "desc": "Büro"},
        {"_type": "transition", "event": "enter", "desc": ""},
        {"_type": "transition", "event": "enter", "desc": "Büro", "tst": "x"},
        [1, 2],
    ):
        assert p.post("/api/owntracks", json=body).status_code == 200
    # only the one with a broken timestamp (counted as now) was stored
    assert len(admin.get("/api/events", params={"from": "2026-01-01", "to": "2027-12-31"}).json()) == 1
