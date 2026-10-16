"""Absence periods (vacation, sickness, ...) and the yearly vacation account."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import VACATION_DAYS, DayEntry, DayKind, User, VacationAllowance
from .reports import local_today, schedule

DEFAULT_VACATION_DAYS = 30.0


@dataclass
class Period:
    start: date
    end: date
    kind: DayKind
    note: str
    workdays: int
    vacation_days: float


@dataclass
class VacationAccount:
    year: int
    configured: bool
    days: float
    carried_over: float
    taken: float  # up to and including today
    planned: float  # after today

    @property
    def total(self) -> float:
        return self.days + self.carried_over

    @property
    def remaining(self) -> float:
        return self.total - self.taken - self.planned


def workdays(db: Session, user: User, start: date, end: date) -> list[date]:
    """Days with a target (per work model) that are no public holiday."""
    return [d for d, base, holiday in schedule(db, user, start, end) if base > 0 and holiday is None]


def set_range(
    db: Session, user: User, start: date, end: date, kind: DayKind, note: str, *, dry_run: bool = False
) -> list[date]:
    """Mark every workday in [start, end] with `kind` (existing entries on those days are replaced)."""
    days = workdays(db, user, start, end)
    if dry_run:
        return days
    existing = {
        e.day: e
        for e in db.scalars(select(DayEntry).where(DayEntry.user_id == user.id, DayEntry.day.in_(days)))
    }
    for d in days:
        entry = existing.get(d) or DayEntry(user_id=user.id, day=d)
        entry.kind = kind
        entry.note = note
        db.add(entry)
    db.commit()
    return days


def delete_range(db: Session, user: User, start: date, end: date) -> int:
    result = db.execute(delete(DayEntry).where(DayEntry.user_id == user.id, DayEntry.day.between(start, end)))
    db.commit()
    return result.rowcount


def periods(db: Session, user: User, start: date, end: date) -> list[Period]:
    """Group day entries into periods: same kind and note, interrupted only by non-workdays."""
    entries = list(
        db.scalars(
            select(DayEntry)
            .where(
                DayEntry.user_id == user.id,
                DayEntry.day.between(start, end),
                DayEntry.kind != DayKind.WORKDAY,
            )
            .order_by(DayEntry.day)
        )
    )
    if not entries:
        return []
    working = set(workdays(db, user, entries[0].day, entries[-1].day))
    out: list[Period] = []
    for e in entries:
        cur = out[-1] if out else None
        gap_free = cur and not any(
            d in working for d in _days_between(cur.end, e.day)
        )  # only weekends/holidays in between
        if cur and cur.kind == e.kind and cur.note == e.note and gap_free:
            cur.end = e.day
        else:
            cur = Period(e.day, e.day, e.kind, e.note, 0, 0.0)
            out.append(cur)
        if e.day in working:
            cur.workdays += 1
            cur.vacation_days += VACATION_DAYS.get(e.kind, 0.0)
    return out


def _days_between(a: date, b: date) -> list[date]:
    """Days strictly between a and b."""
    return [date.fromordinal(o) for o in range(a.toordinal() + 1, b.toordinal())]


def vacation_account(db: Session, user: User, year: int) -> VacationAccount:
    allowance = db.scalar(
        select(VacationAllowance).where(VacationAllowance.user_id == user.id, VacationAllowance.year == year)
    )
    if allowance is None:
        previous = db.scalar(
            select(VacationAllowance)
            .where(VacationAllowance.user_id == user.id, VacationAllowance.year < year)
            .order_by(VacationAllowance.year.desc())
        )
        days, carried, configured = (previous.days if previous else DEFAULT_VACATION_DAYS), 0.0, False
    else:
        days, carried, configured = allowance.days, allowance.carried_over, True

    start, end = date(year, 1, 1), date(year, 12, 31)
    working = set(workdays(db, user, start, end))
    today = local_today(user)
    taken = planned = 0.0
    for e in db.scalars(
        select(DayEntry).where(
            DayEntry.user_id == user.id,
            DayEntry.day.between(start, end),
            DayEntry.kind.in_(list(VACATION_DAYS)),
        )
    ):
        if e.day not in working:
            continue
        if e.day <= today:
            taken += VACATION_DAYS[e.kind]
        else:
            planned += VACATION_DAYS[e.kind]
    return VacationAccount(year, configured, days, carried, taken, planned)


def set_allowance(db: Session, user: User, year: int, days: float, carried_over: float) -> VacationAllowance:
    allowance = db.scalar(
        select(VacationAllowance).where(VacationAllowance.user_id == user.id, VacationAllowance.year == year)
    )
    if allowance is None:
        allowance = VacationAllowance(user_id=user.id, year=year)
        db.add(allowance)
    allowance.days = days
    allowance.carried_over = carried_over
    db.commit()
    return allowance
