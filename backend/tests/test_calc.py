from datetime import UTC, date, datetime

import pytest

from pendel.calc import (
    WARN_BREAK_TOO_SHORT,
    WARN_MAX_WORK_EXCEEDED,
    BreakSpan,
    Rules,
    SessionSpan,
    Span,
    evaluate_day,
    office_gap_counts_as_break,
    required_break,
    target_minutes,
)
from pendel.models import BreakMode, DayKind

DAY = date(2026, 10, 14)
NOW = datetime(2026, 10, 14, 23, 0, tzinfo=UTC)


def t(hhmm: str) -> datetime:
    h, m = map(int, hhmm.split(":"))
    return datetime(2026, 10, 14, h, m, tzinfo=UTC)


def session(start: str, end: str | None, *breaks: tuple[str, str, bool]) -> SessionSpan:
    return SessionSpan(
        t(start), t(end) if end else None, tuple(BreakSpan(t(b), t(e), d) for b, e, d in breaks)
    )


@pytest.mark.parametrize(
    ("entry", "holiday", "expected"),
    [
        (None, False, 480),
        (None, True, 0),
        (DayKind.VACATION, False, 0),
        (DayKind.SICK, False, 0),
        (DayKind.VACATION_HALF, False, 240),
        (DayKind.VACATION_HALF, True, 0),
        (DayKind.FLEX_DAY, False, 480),
        (DayKind.PUBLIC_HOLIDAY, False, 0),
        (DayKind.WORKDAY, True, 480),
    ],
)
def test_target_minutes(entry, holiday, expected):
    assert target_minutes(480, is_holiday=holiday, entry=entry) == expected


def test_office_gap_threshold():
    assert office_gap_counts_as_break(90, 90)
    assert not office_gap_counts_as_break(91, 90)


@pytest.mark.parametrize(("work", "brk"), [(360, 0), (361, 30), (540, 30), (541, 45)])
def test_required_break(work, brk):
    assert required_break(work) == brk


def test_manual_breaks_are_deducted():
    r = evaluate_day(DAY, 480, [session("08:00", "16:30", ("12:00", "12:30", True))], [], Rules(), NOW)
    assert (r.gross, r.breaks_effective, r.actual, r.diff) == (510, 30, 480, 0)
    assert r.warnings == []


def test_absence_not_deducted_counts_as_work():
    # Customer visit recorded as gap but flagged "not a break"
    r = evaluate_day(DAY, 480, [session("08:00", "16:00", ("10:00", "12:30", False))], [], Rules(), NOW)
    assert r.breaks_effective == 0
    assert r.actual == 480


def test_auto_break_tops_up_recorded_breaks():
    rules = Rules(break_mode=BreakMode.AUTO, auto_break_minutes=45)
    short = evaluate_day(DAY, 480, [session("08:00", "17:00", ("12:00", "12:15", True))], [], rules, NOW)
    assert short.breaks_effective == 45
    long = evaluate_day(DAY, 480, [session("08:00", "17:00", ("12:00", "13:00", True))], [], rules, NOW)
    assert long.breaks_effective == 60


def test_auto_break_respects_minimum_work_time():
    rules = Rules(break_mode=BreakMode.AUTO, auto_break_minutes=30, auto_break_min_work_minutes=360)
    r = evaluate_day(DAY, 240, [session("08:00", "12:00")], [], rules, NOW)
    assert r.breaks_effective == 0
    assert r.actual == 240


def test_missing_legal_break_warns():
    r = evaluate_day(DAY, 480, [session("08:00", "15:00")], [], Rules(), NOW)
    assert WARN_BREAK_TOO_SHORT in r.warnings
    off = evaluate_day(DAY, 480, [session("08:00", "15:00")], [], Rules(legal_break_check=False), NOW)
    assert off.warnings == []


def test_max_work_warning():
    r = evaluate_day(DAY, 480, [session("06:00", "17:30", ("12:00", "12:45", True))], [], Rules(), NOW)
    assert WARN_MAX_WORK_EXCEEDED in r.warnings


def test_commute_credit():
    commutes = [Span(t("07:00"), t("07:40")), Span(t("16:30"), t("17:10"))]
    sessions = [session("07:40", "16:10", ("12:00", "12:30", True))]
    none = evaluate_day(DAY, 480, sessions, commutes, Rules(), NOW)
    assert (none.commute, none.commute_credit, none.actual) == (80, 0, 480)
    half = evaluate_day(DAY, 480, sessions, commutes, Rules(commute_credit_percent=50), NOW)
    assert (half.commute_credit, half.actual, half.diff) == (40, 520, 40)


def test_running_session_uses_now():
    r = evaluate_day(DAY, 480, [session("08:00", None)], [], Rules(legal_break_check=False), t("10:00"))
    assert r.actual == 120


def test_empty_day_is_minus_target():
    r = evaluate_day(DAY, 480, [], [], Rules(break_mode=BreakMode.AUTO), NOW)
    assert (r.actual, r.breaks_effective, r.diff) == (0, 0, -480)
