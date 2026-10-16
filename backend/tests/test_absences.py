def test_vacation_range_skips_weekends_and_holidays(admin):
    # Tue 22 Dec 2026 – Fri 1 Jan 2027: 25/26 Dec and 1 Jan are holidays, 26/27 Dec weekend
    body = {"start": "2026-12-22", "end": "2027-01-01", "kind": "vacation", "note": "Weihnachten"}
    preview = admin.post("/api/absences", json=body, params={"dry_run": True}).json()
    assert preview["days"] == [
        "2026-12-22",
        "2026-12-23",
        "2026-12-24",
        "2026-12-28",
        "2026-12-29",
        "2026-12-30",
        "2026-12-31",
    ]
    assert preview["vacation_days"] == 7
    assert admin.get("/api/days", params={"from": "2026-12-01", "to": "2026-12-31"}).json() == []

    assert admin.post("/api/absences", json=body).status_code == 200
    data = admin.get("/api/absences", params={"year": 2026}).json()
    (period,) = data["periods"]
    assert (period["start"], period["end"], period["workdays"], period["vacation_days"]) == (
        "2026-12-22",
        "2026-12-31",
        7,
        7.0,
    )
    assert data["account"]["days"] == 30 and data["account"]["configured"] is False
    # 2027 only has 1 Jan (holiday) in the range -> nothing
    assert admin.get("/api/absences", params={"year": 2027}).json()["periods"] == []

    rep = admin.get("/api/report", params={"from": "2026-12-22", "to": "2026-12-24"}).json()
    assert [d["target"] for d in rep["days"]] == [0, 0, 0]


def test_vacation_account(admin):
    admin.put("/api/vacation/2025", json={"days": 28, "carried_over": 0})
    acc = admin.put("/api/vacation/2026", json={"days": 30, "carried_over": 2.5}).json()
    assert (acc["total"], acc["configured"], acc["suggested_carry_over"]) == (32.5, True, 28)
    admin.post("/api/absences", json={"start": "2026-03-02", "end": "2026-03-06", "kind": "vacation"})
    admin.put("/api/days/2026-03-09", json={"kind": "vacation_half"})
    admin.put("/api/days/2026-03-07", json={"kind": "vacation"})  # Saturday: not charged
    acc = admin.get("/api/vacation/2026").json()
    assert acc["taken"] + acc["planned"] == 5.5
    assert acc["remaining"] == 27
    # next year without allowance inherits the days, not the carry-over
    nxt = admin.get("/api/vacation/2027").json()
    assert (nxt["days"], nxt["carried_over"], nxt["configured"]) == (30, 0, False)


def test_other_absence_kinds_are_neutral_and_grouped(admin):
    admin.post("/api/absences", json={"start": "2026-11-02", "end": "2026-11-04", "kind": "sick_child"})
    admin.post(
        "/api/absences", json={"start": "2026-11-05", "end": "2026-11-05", "kind": "training", "note": "Kurs"}
    )
    admin.post("/api/absences", json={"start": "2026-11-06", "end": "2026-11-06", "kind": "release"})
    periods = admin.get("/api/absences", params={"year": 2026}).json()["periods"]
    assert [(p["kind"], p["workdays"], p["vacation_days"]) for p in periods] == [
        ("sick_child", 3, 0),
        ("training", 1, 0),
        ("release", 1, 0),
    ]
    rep = admin.get("/api/report", params={"from": "2026-11-02", "to": "2026-11-06"}).json()
    assert all(d["target"] == 0 for d in rep["days"])


def test_overwrite_and_delete_range(admin):
    admin.post("/api/absences", json={"start": "2026-11-09", "end": "2026-11-13", "kind": "vacation"})
    admin.post("/api/absences", json={"start": "2026-11-11", "end": "2026-11-11", "kind": "sick"})
    kinds = [p["kind"] for p in admin.get("/api/absences", params={"year": 2026}).json()["periods"]]
    assert kinds == ["vacation", "sick", "vacation"]
    assert admin.delete("/api/absences", params={"from": "2026-11-09", "to": "2026-11-13"}).status_code == 204
    assert admin.get("/api/absences", params={"year": 2026}).json()["periods"] == []


def test_invalid_absence(admin):
    bad = admin.post("/api/absences", json={"start": "2026-11-10", "end": "2026-11-09", "kind": "vacation"})
    assert bad.status_code == 422
    work = admin.post("/api/absences", json={"start": "2026-11-10", "end": "2026-11-10", "kind": "workday"})
    assert work.status_code == 422
