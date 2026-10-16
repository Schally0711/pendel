from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from pendel.models import utcnow


def local_today() -> date:
    return utcnow().astimezone(ZoneInfo("Europe/Berlin")).date()


def _setup_history(admin, start: date) -> None:
    """Move the default employment and work model back to `start`, with an opening balance."""
    emp = admin.get("/api/employments").json()[0]
    model = admin.get("/api/work-models").json()[0]
    assert admin.put(f"/api/employments/{emp['id']}", json={"start": str(start)}).status_code == 200
    assert (
        admin.put(f"/api/work-models/{model['id']}", json={**model, "valid_from": str(start)}).status_code
        == 200
    )
    assert admin.post("/api/adjustments", json={"day": str(start), "minutes": 600}).status_code == 201


def _diff_sum(admin, start: date, end: date) -> int:
    days = admin.get("/api/report", params={"from": str(start), "to": str(end)}).json()["days"]
    return sum(d["diff"] for d in days)


def test_new_user_has_current_employment(admin):
    emps = admin.get("/api/employments").json()
    assert len(emps) == 1 and emps[0]["current"] and emps[0]["end"] is None


def test_switch_starts_fresh_balance_and_vacation(admin):
    today = local_today()
    first, switch = today - timedelta(days=60), today - timedelta(days=10)
    _setup_history(admin, first)

    r = admin.post(
        "/api/employments/switch", json={"employer": "Neu GmbH", "start": str(switch), "vacation_days": 5}
    )
    assert r.status_code == 201, r.text
    old, new = admin.get("/api/employments").json()
    assert old["end"] == str(switch - timedelta(days=1)) and not old["current"]
    assert new["current"] and new["employer"] == "Neu GmbH"

    # the old account keeps its opening balance, the new one starts from zero
    assert old["balance"] == 600 + _diff_sum(admin, first, switch - timedelta(days=1))
    assert new["balance"] == _diff_sum(admin, switch, today)
    assert admin.get("/api/today").json()["balance"] == new["balance"]

    # the work model was copied to the start of the new job
    models = admin.get("/api/work-models").json()
    assert [m["valid_from"] for m in models] == [str(first), str(switch)]

    if switch.year == today.year:
        acc = admin.get(f"/api/vacation/{today.year}").json()
        assert (acc["employment_id"], acc["days"], acc["suggested_carry_over"]) == (new["id"], 5, 0)


def test_gap_between_employments_has_no_target(admin):
    today = local_today()
    _setup_history(admin, today - timedelta(days=60))
    emp = admin.get("/api/employments").json()[0]
    gap_start, new_start = today - timedelta(days=30), today - timedelta(days=20)
    r = admin.post(
        "/api/employments/switch",
        json={"start": str(new_start), "previous_end": str(gap_start - timedelta(days=1))},
    )
    assert r.status_code == 201, r.text
    days = admin.get(
        "/api/report", params={"from": str(gap_start), "to": str(new_start - timedelta(days=1))}
    ).json()["days"]
    assert all(d["target"] == 0 for d in days)
    assert admin.get("/api/employments").json()[0]["id"] == emp["id"]


def test_invalid_employment_changes(admin):
    today = local_today()
    _setup_history(admin, today - timedelta(days=60))
    first = admin.get("/api/employments").json()[0]
    assert admin.post("/api/employments/switch", json={"start": str(first["start"])}).status_code == 400
    switch = today - timedelta(days=10)
    admin.post("/api/employments/switch", json={"start": str(switch)})
    old, new = admin.get("/api/employments").json()
    # overlapping periods and deleting the current job are refused
    r = admin.put(f"/api/employments/{new['id']}", json={"start": str(today - timedelta(days=30))})
    assert r.status_code == 400 and r.json()["detail"] == "employment_overlap"
    assert admin.delete(f"/api/employments/{new['id']}").status_code == 400
    r = admin.put(f"/api/employments/{old['id']}", json={"start": old["start"], "end": None})
    assert r.json()["detail"] == "employment_open_not_last"


def test_delete_archived_employment_with_data(admin):
    today = local_today()
    first, switch = today - timedelta(days=60), today - timedelta(days=10)
    _setup_history(admin, first)
    day = first + timedelta(days=1)
    at = lambda h: datetime.combine(day, time(h), ZoneInfo("Europe/Berlin")).isoformat()  # noqa: E731
    admin.post("/api/sessions", json={"kind": "home", "start": at(8), "end": at(12)})
    admin.put(f"/api/days/{first + timedelta(days=2)}", json={"kind": "vacation"})
    admin.post("/api/employments/switch", json={"start": str(switch)})
    old, new = admin.get("/api/employments").json()

    assert admin.delete(f"/api/employments/{old['id']}").status_code == 204
    assert [e["id"] for e in admin.get("/api/employments").json()] == [new["id"]]
    rng = {"from": str(first), "to": str(switch - timedelta(days=1))}
    assert admin.get("/api/sessions", params=rng).json() == []
    assert admin.get("/api/adjustments").json() == []
    assert all(d["entry"] is None for d in admin.get("/api/report", params=rng).json()["days"])
    assert [m["valid_from"] for m in admin.get("/api/work-models").json()] == [str(switch)]
