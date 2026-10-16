"""Day-by-day evaluation of a user's data and the resulting flexitime balance."""

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import holidays
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .calc import BreakSpan, DayResult, Rules, SessionSpan, Span, evaluate_day, target_minutes
from .models import BalanceAdjustment, Commute, DayEntry, User, WorkModel, WorkSession


def holiday_calendar(user: User, years: range) -> holidays.HolidayBase:
    return holidays.country_holidays(user.country, subdiv=user.subdivision, years=years)


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
    for s in db.scalars(
        select(WorkSession)
        .where(WorkSession.user_id == user.id, WorkSession.start >= lo, WorkSession.start < hi)
        .options(selectinload(WorkSession.breaks))
    ):
        breaks = tuple(BreakSpan(b.start, b.end, b.deducted) for b in s.breaks)
        sessions[s.start.astimezone(tz).date()].append(SessionSpan(s.start, s.end, breaks))
    commutes: dict[date, list[Span]] = defaultdict(list)
    for c in db.scalars(
        select(Commute).where(Commute.user_id == user.id, Commute.start >= lo, Commute.start < hi)
    ):
        commutes[c.start.astimezone(tz).date()].append(Span(c.start, c.end))

    cal = holiday_calendar(user, range(start.year, end.year + 1))
    results = []
    day = start
    while day <= end:
        model = _active_model(models, day)
        base = model.target_minutes_for_weekday(day.weekday()) if model else 0
        target = target_minutes(base, is_holiday=day in cal, entry=entries.get(day))
        results.append(evaluate_day(day, target, sessions[day], commutes[day], _rules(model), now))
        day += timedelta(days=1)
    return results


def balance(db: Session, user: User, until: date, now: datetime | None = None) -> int:
    """Flexitime balance in minutes at the end of `until`: adjustments plus (actual - target) per day."""
    adjustments = db.scalar(
        select(func.coalesce(func.sum(BalanceAdjustment.minutes), 0)).where(
            BalanceAdjustment.user_id == user.id, BalanceAdjustment.day <= until
        )
    )
    first_model = db.scalar(select(func.min(WorkModel.valid_from)).where(WorkModel.user_id == user.id))
    if first_model is None or first_model > until:
        return adjustments
    return adjustments + sum(r.diff for r in evaluate_range(db, user, first_model, until, now))
