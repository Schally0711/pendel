from datetime import UTC, date, datetime, timedelta

import pytest

from pendel.db import get_engine, get_sessionmaker, migrate
from pendel.models import (
    BalanceAdjustment,
    Break,
    DayEntry,
    DayKind,
    PlaceKind,
    User,
    WorkModel,
    WorkSession,
)
from pendel.reports import balance, evaluate_range


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("PENDEL_DATA_DIR", str(tmp_path))
    from pendel.config import get_settings

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    migrate()
    with get_sessionmaker()() as session:
        yield session


@pytest.fixture
def user(db):
    u = User(email="a@example.org", password_hash="x", display_name="A", subdivision="NW")
    u.work_models.append(WorkModel(valid_from=date(2026, 9, 28)))  # Mon, 40 h week
    db.add(u)
    db.commit()
    return u


def work(db, user, day: date, start: str, end: str, brk: int = 30) -> None:
    """Add an office session in local time (Europe/Berlin is UTC+2 in early October)."""
    s_h, s_m = map(int, start.split(":"))
    e_h, e_m = map(int, end.split(":"))
    begin = datetime(day.year, day.month, day.day, s_h, s_m, tzinfo=UTC) - timedelta(hours=2)
    finish = datetime(day.year, day.month, day.day, e_h, e_m, tzinfo=UTC) - timedelta(hours=2)
    s = WorkSession(user_id=user.id, kind=PlaceKind.OFFICE, start=begin, end=finish)
    if brk:
        s.breaks.append(Break(start=begin + timedelta(hours=4), end=begin + timedelta(hours=4, minutes=brk)))
    db.add(s)
    db.commit()


def test_week_with_holiday_and_vacation(db, user):
    # Week 2026-09-28 .. 2026-10-04: Sat 3 Oct is a holiday (weekend anyway)
    work(db, user, date(2026, 9, 28), "08:00", "17:00")  # +30
    work(db, user, date(2026, 9, 29), "08:00", "16:30")  # 0
    db.add(DayEntry(user_id=user.id, day=date(2026, 9, 30), kind=DayKind.VACATION))
    work(db, user, date(2026, 10, 1), "08:00", "16:00")  # -30
    # Friday 2 Oct: nothing recorded -> -480
    db.commit()

    days = evaluate_range(db, user, date(2026, 9, 28), date(2026, 10, 4))
    assert [d.diff for d in days] == [30, 0, 0, -30, -480, 0, 0]
    assert balance(db, user, date(2026, 10, 4)) == -480


def test_nrw_holiday_has_no_target(db, user):
    # Allerheiligen 2027-11-01 is a Monday and a holiday in NRW
    (d,) = evaluate_range(db, user, date(2027, 11, 1), date(2027, 11, 1))
    assert d.target == 0


def test_opening_balance(db, user):
    db.add(BalanceAdjustment(user_id=user.id, day=date(2026, 9, 27), minutes=600, note="opening balance"))
    db.commit()
    assert balance(db, user, date(2026, 9, 27)) == 600
    # first workday without any record: 600 - 480
    assert balance(db, user, date(2026, 9, 28)) == 120


def test_session_attributed_to_local_day(db, user):
    # 00:30 local on 1 Oct is still 30 Sep in UTC
    work(db, user, date(2026, 10, 1), "00:30", "01:30", brk=0)
    sep30, oct1 = evaluate_range(db, user, date(2026, 9, 30), date(2026, 10, 1))
    assert sep30.actual == 0
    assert oct1.actual == 60


def test_work_model_change(db, user):
    db.add(WorkModel(user_id=user.id, valid_from=date(2026, 10, 5), target_fri=0))  # Friday off from then on
    db.commit()
    fri_before, fri_after = evaluate_range(db, user, date(2026, 10, 2), date(2026, 10, 9))[::7]
    assert (fri_before.target, fri_after.target) == (480, 0)
