"""Day-by-day evaluation of a user's data and the resulting flexitime balance."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import holidays
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .calc import BreakSpan, DayResult, Rules, SessionSpan, Span, evaluate_day, target_minutes
from .employments import covered, employments, latest_started
from .models import BalanceAdjustment, Commute, DayEntry, DayKind, PlaceKind, User, WorkModel, WorkSession


@dataclass
class DayReport:
    result: DayResult
    holiday: str | None = None
    entry: DayKind | None = None
    kinds: list[PlaceKind] = field(default_factory=list)  # where work happened


def holiday_calendar(user: User, years: range) -> holidays.HolidayBase:
    language = "en_US" if user.locale == "en" else None  # None = country default (German for DE)
    return holidays.country_holidays(user.country, subdiv=user.subdivision, years=years, language=language)


def _utc_bounds(start: date, end: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    lo = datetime.combine(start, time.min, tz).astimezone(UTC)
    hi = datetime.combine(end + timedelta(days=1), time.min, tz).astimezone(UTC)
    return lo, hi


def _active_model(models: list[WorkModel], day: date) -> WorkModel | None:
    active = None
    for m in models:  # sorted by valid_from
        if m.valid_from <= day:
            active = m
    return active


def _rules(model: WorkModel | None) -> Rules:
    if model is None:
        return Rules()
    return Rules(
        break_mode=model.break_mode,
        auto_break_minutes=model.auto_break_minutes,
        auto_break_min_work_minutes=model.auto_break_min_work_minutes,
        legal_break_check=model.legal_break_check,
        commute_credit_percent=model.commute_credit_percent,
    )


def evaluate_range(
    db: Session, user: User, start: date, end: date, now: datetime | None = None
) -> list[DayResult]:
    """Evaluate every day in [start, end]. Days before the first work model have no target."""
    return [d.result for d in evaluate_days(db, user, start, end, now)]


def evaluate_days(
    db: Session, user: User, start: date, end: date, now: datetime | None = None
) -> list[DayReport]:
    """Like `evaluate_range`, with holiday names, day entries and work locations."""
    now = now or datetime.now(UTC)
    tz = ZoneInfo(user.timezone)
    lo, hi = _utc_bounds(start, end, tz)

    models = list(
        db.scalars(select(WorkModel).where(WorkModel.user_id == user.id).order_by(WorkModel.valid_from))
    )
    entries = {
        e.day: e.kind
        for e in db.scalars(
            select(DayEntry).where(DayEntry.user_id == user.id, DayEntry.day.between(start, end))
        )
    }
    sessions: dict[date, list[SessionSpan]] = defaultdict(list)
    kinds: dict[date, list[PlaceKind]] = defaultdict(list)
    for s in db.scalars(
        select(WorkSession)
        .where(WorkSession.user_id == user.id, WorkSession.start >= lo, WorkSession.start < hi)
        .options(selectinload(WorkSession.breaks))
    ):
        breaks = tuple(BreakSpan(b.start, b.end, b.deducted) for b in s.breaks)
        local_day = s.start.astimezone(tz).date()
        sessions[local_day].append(SessionSpan(s.start, s.end, breaks))
        if s.kind not in kinds[local_day]:
            kinds[local_day].append(s.kind)
    commutes: dict[date, list[Span]] = defaultdict(list)
    for c in db.scalars(
        select(Commute).where(Commute.user_id == user.id, Commute.start >= lo, Commute.start < hi)
    ):
        commutes[c.start.astimezone(tz).date()].append(Span(c.start, c.end))

    emps = employments(db, user)
    cal = holiday_calendar(user, range(start.year, end.year + 1))
    results = []
    day = start
    while day <= end:
        model = _active_model(models, day)
        base = model.target_minutes_for_weekday(day.weekday()) if model and covered(emps, day) else 0
        holiday = cal.get(day)
        entry = entries.get(day)
        target = target_minutes(base, is_holiday=holiday is not None, entry=entry)
        result = evaluate_day(day, target, sessions[day], commutes[day], _rules(model), now)
        results.append(DayReport(result, holiday, entry, kinds[day]))
        day += timedelta(days=1)
    return results


def schedule(db: Session, user: User, start: date, end: date) -> list[tuple[date, int, str | None]]:
    """(day, weekday target of the active work model, holiday name) for every day in [start, end].

    Used for absences: days before the first work model use that first model, so vacation from
    before someone started using Pendel is still counted as workdays. Days outside every
    employment (gaps between jobs) have no target.
    """
    models = list(
        db.scalars(select(WorkModel).where(WorkModel.user_id == user.id).order_by(WorkModel.valid_from))
    )
    emps = employments(db, user)
    cal = holiday_calendar(user, range(start.year, end.year + 1))
    out = []
    day = start
    while day <= end:
        model = _active_model(models, day) or (models[0] if models else None)
        base = model.target_minutes_for_weekday(day.weekday()) if model and covered(emps, day) else 0
        out.append((day, base, cal.get(day)))
        day += timedelta(days=1)
    return out


def local_today(user: User, now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(ZoneInfo(user.timezone)).date()


def balance(db: Session, user: User, until: date, now: datetime | None = None) -> int:
    """Flexitime balance in minutes at the end of `until`: adjustments plus (actual - target) per day.

    Days after today do not count yet (their target is not due). Each employment starts from
    zero: only its own days and adjustments count.
    """
    until = min(until, local_today(user, now))
    emp = latest_started(employments(db, user), until)
    since = emp.start if emp else date.min
    adjustments = db.scalar(
        select(func.coalesce(func.sum(BalanceAdjustment.minutes), 0)).where(
            BalanceAdjustment.user_id == user.id, BalanceAdjustment.day.between(since, until)
        )
    )
    first_model = db.scalar(select(func.min(WorkModel.valid_from)).where(WorkModel.user_id == user.id))
    if first_model is None or first_model > until:
        return adjustments
    start = max(first_model, since)
    return adjustments + sum(r.diff for r in evaluate_range(db, user, start, until, now))
