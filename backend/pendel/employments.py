"""Employments (jobs): each one starts a fresh flexitime balance and vacation account.

Days between employments or after the last one ended have no target. Ended employments stay as
an archive (history, statistics, reports keep working) and can be deleted together with their data.
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import (
    BalanceAdjustment,
    Commute,
    DayEntry,
    Employment,
    Event,
    User,
    VacationAllowance,
    WorkModel,
    WorkSession,
)


class EmploymentError(ValueError):
    """Invalid employment change; the message is an API error code."""


def employments(db: Session, user: User) -> list[Employment]:
    return list(
        db.scalars(select(Employment).where(Employment.user_id == user.id).order_by(Employment.start))
    )


def employment_on(emps: list[Employment], day: date) -> Employment | None:
    """The employment covering `day`, if any."""
    for e in emps:
        if e.start <= day and (e.end is None or day <= e.end):
            return e
    return None


def latest_started(emps: list[Employment], day: date) -> Employment | None:
    """The last employment that started on or before `day` (it may have ended already)."""
    found = None
    for e in emps:  # sorted by start
        if e.start <= day:
            found = e
    return found


def covered(emps: list[Employment], day: date) -> bool:
    """Whether `day` can have a target: inside an employment, or before the first one (so vacation
    from before someone started using Pendel still counts). Gaps between jobs and days after the
    last one ended have none."""
    return not emps or day < emps[0].start or employment_on(emps, day) is not None


def validate(emps: list[Employment]) -> None:
    """Employments must not overlap; only the last one may be open-ended."""
    ordered = sorted(emps, key=lambda e: e.start)
    for i, e in enumerate(ordered):
        if e.end is not None and e.end < e.start:
            raise EmploymentError("employment_end_before_start")
        if i + 1 < len(ordered):
            nxt = ordered[i + 1]
            if e.end is None:
                raise EmploymentError("employment_open_not_last")
            if e.end >= nxt.start:
                raise EmploymentError("employment_overlap")


def switch(
    db: Session,
    user: User,
    *,
    employer: str,
    start: date,
    previous_end: date | None = None,
    vacation_days: float | None = None,
) -> Employment:
    """Change jobs: end the current employment and start a new one.

    The work model active before `start` is copied to `start`, so it can be adjusted afterwards;
    the vacation entitlement of the start year is set if given (e.g. pro rata).
    """
    emps = employments(db, user)
    current = latest_started(emps, start - timedelta(days=1))
    if any(e.start >= start for e in emps):
        raise EmploymentError("employment_overlap")
    previous_end = previous_end or start - timedelta(days=1)
    if current is not None and (current.end is None or current.end >= start):
        if previous_end >= start or previous_end < current.start:
            raise EmploymentError("employment_invalid_end")
        current.end = previous_end
    new = Employment(user_id=user.id, employer=employer.strip(), start=start)
    db.add(new)
    validate([*emps, new])

    models = list(
        db.scalars(select(WorkModel).where(WorkModel.user_id == user.id).order_by(WorkModel.valid_from))
    )
    if not any(m.valid_from == start for m in models):
        template = next((m for m in reversed(models) if m.valid_from < start), None)
        copy = WorkModel(user_id=user.id, valid_from=start)
        if template is not None:
            for col in WorkModel.__table__.columns:
                if col.key not in ("id", "user_id", "valid_from"):
                    setattr(copy, col.key, getattr(template, col.key))
        db.add(copy)
    db.flush()
    if vacation_days is not None:
        db.add(
            VacationAllowance(
                user_id=user.id, employment_id=new.id, year=start.year, days=vacation_days, carried_over=0
            )
        )
    db.commit()
    return new


def delete_with_data(db: Session, user: User, emp: Employment) -> None:
    """Delete an ended employment and everything recorded within it."""
    if emp.end is None:
        raise EmploymentError("employment_still_active")
    emps = employments(db, user)
    later = [e for e in emps if e.start > emp.end]
    if not later:
        raise EmploymentError("employment_still_active")
    tz = ZoneInfo(user.timezone)
    lo = datetime.combine(emp.start, time.min, tz).astimezone(UTC)
    hi = datetime.combine(emp.end + timedelta(days=1), time.min, tz).astimezone(UTC)
    for model in (WorkSession, Commute):
        db.execute(delete(model).where(model.user_id == user.id, model.start >= lo, model.start < hi))
    db.execute(delete(Event).where(Event.user_id == user.id, Event.occurred_at >= lo, Event.occurred_at < hi))
    db.execute(delete(DayEntry).where(DayEntry.user_id == user.id, DayEntry.day.between(emp.start, emp.end)))
    db.execute(
        delete(BalanceAdjustment).where(
            BalanceAdjustment.user_id == user.id, BalanceAdjustment.day.between(emp.start, emp.end)
        )
    )
    # Work models that only served this employment; the next one must keep a model at its start.
    nxt = later[0]
    models = list(
        db.scalars(select(WorkModel).where(WorkModel.user_id == user.id).order_by(WorkModel.valid_from))
    )
    inside = [m for m in models if emp.start <= m.valid_from <= emp.end]
    if inside and not any(emp.end < m.valid_from <= nxt.start for m in models):
        inside[-1].valid_from = nxt.start
        inside = inside[:-1]
    for m in inside:
        db.delete(m)
    db.delete(emp)  # vacation allowances cascade
    db.commit()
