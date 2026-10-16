"""Statistics over a date range: daily series, weekly/monthly aggregates, summary, tax overview."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Commute, CommuteDirection, DayKind, Place, PlaceKind, User, WorkSession
from .reports import balance, evaluate_days, local_today


@dataclass
class DayStat:
    day: date
    target: int
    actual: int
    diff: int
    balance: int  # flexitime balance at the end of the day
    place: str | None  # office / home / other (office wins on mixed days)
    entry: DayKind | None
    holiday: str | None
    start: int | None  # minutes after midnight (local) of the first session
    end: int | None  # minutes after midnight of the last session end
    breaks: int
    commute_to: int
    commute_from: int
    warnings: int


@dataclass
class Period:
    key: str  # "2026-W42" or "2026-10"
    start: date
    end: date
    target: int = 0
    actual: int = 0
    diff: int = 0
    office_days: int = 0
    home_days: int = 0
    absence_days: int = 0


@dataclass
class Summary:
    worked_days: int = 0
    target: int = 0
    actual: int = 0
    diff: int = 0
    balance_start: int = 0
    balance_end: int = 0
    avg_actual: float = 0
    office_days: int = 0
    home_days: int = 0
    other_days: int = 0
    absence_days: dict[str, int] = field(default_factory=dict)
    avg_start: float | None = None
    avg_end: float | None = None
    earliest_start: int | None = None
    latest_end: int | None = None
    avg_commute_to: float | None = None
    avg_commute_from: float | None = None
    commute_by_weekday: list[float | None] = field(default_factory=list)  # Monday first, to + from
    longest_day: date | None = None
    longest_minutes: int = 0
    overtime_days: int = 0
    warning_days: int = 0


def _local_minutes(dt, tz: ZoneInfo) -> int:
    local = dt.astimezone(tz)
    return local.hour * 60 + local.minute


def _avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def day_stats(db: Session, user: User, start: date, end: date) -> list[DayStat]:
    """Per-day figures for [start, end], capped at today (future days have no data yet)."""
    end = min(end, local_today(user))
    if end < start:
        return []
    tz = ZoneInfo(user.timezone)
    reports = evaluate_days(db, user, start, end)

    lo = start - timedelta(days=1)
    hi = end + timedelta(days=1)
    first: dict[date, int] = {}
    last: dict[date, int] = {}
    for s in db.scalars(
        select(WorkSession).where(
            WorkSession.user_id == user.id,
            WorkSession.start >= _utc(lo, tz),
            WorkSession.start < _utc(hi, tz),
        )
    ):
        d = s.start.astimezone(tz).date()
        first[d] = min(first.get(d, 24 * 60), _local_minutes(s.start, tz))
        if s.end:
            end_day = s.end.astimezone(tz).date()
            minutes = _local_minutes(s.end, tz) + (24 * 60 if end_day > d else 0)
            last[d] = max(last.get(d, 0), minutes)
    commute: dict[tuple[date, CommuteDirection], int] = defaultdict(int)
    for c in db.scalars(
        select(Commute).where(
            Commute.user_id == user.id, Commute.start >= _utc(lo, tz), Commute.start < _utc(hi, tz)
        )
    ):
        if c.end:
            commute[(c.start.astimezone(tz).date(), c.direction)] += round(
                (c.end - c.start).total_seconds() / 60
            )

    running = balance(db, user, start - timedelta(days=1))
    today = local_today(user)
    out = []
    for r in reports:
        res = r.result
        # Today is not over: its target only counts as far as it has been worked, so the
        # statistics don't show a dip every morning (a missing day becomes visible tomorrow).
        target = min(res.target, res.actual) if res.day == today else res.target
        diff = res.actual - target
        running += diff
        place = (
            PlaceKind.OFFICE.value if PlaceKind.OFFICE in r.kinds else (r.kinds[0].value if r.kinds else None)
        )
        out.append(
            DayStat(
                day=res.day,
                target=target,
                actual=res.actual,
                diff=diff,
                balance=running,
                place=place,
                entry=r.entry,
                holiday=r.holiday,
                start=first.get(res.day),
                end=last.get(res.day),
                breaks=res.breaks_effective,
                commute_to=commute[(res.day, CommuteDirection.TO_WORK)],
                commute_from=commute[(res.day, CommuteDirection.FROM_WORK)],
                warnings=len(res.warnings),
            )
        )
    return out


def _utc(d: date, tz: ZoneInfo) -> datetime:
    """Start of a local day (aware, so comparisons with stored UTC values work)."""
    return datetime.combine(d, time.min, tz)


def aggregate(days: list[DayStat], by: str) -> list[Period]:
    """Group days by ISO week ("week") or calendar month ("month")."""
    periods: dict[str, Period] = {}
    for d in days:
        if by == "week":
            iso = d.day.isocalendar()
            key = f"{iso.year}-W{iso.week:02d}"
            p_start = d.day - timedelta(days=d.day.weekday())
            p_end = p_start + timedelta(days=6)
        else:
            key = d.day.strftime("%Y-%m")
            p_start = d.day.replace(day=1)
            p_end = (p_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        p = periods.setdefault(key, Period(key, p_start, p_end))
        p.target += d.target
        p.actual += d.actual
        p.diff += d.diff
        if d.place == PlaceKind.OFFICE.value:
            p.office_days += 1
        elif d.place == PlaceKind.HOME.value:
            p.home_days += 1
        if d.entry and d.entry not in (DayKind.WORKDAY, DayKind.PUBLIC_HOLIDAY):
            p.absence_days += 1
    return list(periods.values())


def summarize(days: list[DayStat]) -> Summary:
    s = Summary()
    if not days:
        return s
    s.balance_start = days[0].balance - days[0].diff
    s.balance_end = days[-1].balance
    absences: dict[str, int] = defaultdict(int)
    starts, ends, to, back = [], [], [], []
    by_weekday: dict[int, list[int]] = defaultdict(list)
    for d in days:
        s.target += d.target
        s.actual += d.actual
        s.diff += d.diff
        if d.actual > 0:
            s.worked_days += 1
            if d.actual > s.longest_minutes:
                s.longest_minutes, s.longest_day = d.actual, d.day
        if d.diff > 0 and d.actual > 0:
            s.overtime_days += 1
        if d.warnings:
            s.warning_days += 1
        if d.place == PlaceKind.OFFICE.value:
            s.office_days += 1
        elif d.place == PlaceKind.HOME.value:
            s.home_days += 1
        elif d.place:
            s.other_days += 1
        if d.entry and d.entry not in (DayKind.WORKDAY, DayKind.PUBLIC_HOLIDAY):
            absences[d.entry.value] += 1
        if d.start is not None:
            starts.append(d.start)
        if d.end is not None:
            ends.append(d.end)
        if d.commute_to:
            to.append(d.commute_to)
        if d.commute_from:
            back.append(d.commute_from)
        if d.commute_to or d.commute_from:
            by_weekday[d.day.weekday()].append(d.commute_to + d.commute_from)
    s.avg_actual = s.actual / s.worked_days if s.worked_days else 0
    s.absence_days = dict(absences)
    s.avg_start, s.avg_end = _avg(starts), _avg(ends)
    s.earliest_start = min(starts) if starts else None
    s.latest_end = max(ends) if ends else None
    s.avg_commute_to, s.avg_commute_from = _avg(to), _avg(back)
    s.commute_by_weekday = [_avg(by_weekday[i]) for i in range(7)]
    return s


# --- tax overview (Germany) ---------------------------------------------------------------------

# Entfernungspauschale per km of one-way distance: (rate for km 1-20, rate from km 21)
COMMUTER_RATES = {
    2021: (0.30, 0.35),
    2022: (0.30, 0.38),
    2023: (0.30, 0.38),
    2024: (0.30, 0.38),
    2025: (0.30, 0.38),
}
COMMUTER_RATE_FROM_2026 = (0.38, 0.38)  # 38 ct from the first km since 2026
COMMUTER_RATE_BEFORE_2021 = (0.30, 0.30)
# Homeoffice-Pauschale: (EUR per day, max days)
HOME_OFFICE_RATES = {2020: (5.0, 120), 2021: (5.0, 120), 2022: (5.0, 120)}
HOME_OFFICE_RATE_FROM_2023 = (6.0, 210)


def commuter_rate(year: int) -> tuple[float, float]:
    if year >= 2026:
        return COMMUTER_RATE_FROM_2026
    return COMMUTER_RATES.get(year, COMMUTER_RATE_BEFORE_2021)


def home_office_rate(year: int) -> tuple[float, int]:
    if year >= 2023:
        return HOME_OFFICE_RATE_FROM_2023
    return HOME_OFFICE_RATES.get(year, (0.0, 0))


def commuter_allowance(km: float, year: int) -> float:
    first, rest = commuter_rate(year)
    return min(km, 20) * first + max(km - 20, 0) * rest


@dataclass
class TaxOffice:
    place: str
    distance_km: float | None
    days: int
    amount: float


@dataclass
class TaxOverview:
    year: int
    until: date
    offices: list[TaxOffice]
    office_days: int
    commuter_total: float
    commuter_rate: tuple[float, float]
    home_office_days: int
    home_office_days_counted: int
    home_office_rate: float
    home_office_max_days: int
    home_office_total: float
    missing_distance: bool


def tax_overview(db: Session, user: User, year: int) -> TaxOverview:
    """Office days (any office session) and home-office days (home work without office that day)."""
    start, end = date(year, 1, 1), min(date(year, 12, 31), local_today(user))
    tz = ZoneInfo(user.timezone)
    places = {p.id: p for p in db.scalars(select(Place).where(Place.user_id == user.id))}
    default_office = next((p for p in places.values() if p.kind == PlaceKind.OFFICE and not p.archived), None)
    office_by_day: dict[date, Place | None] = {}
    home_days: set[date] = set()
    if end >= start:
        for s in db.scalars(
            select(WorkSession)
            .where(
                WorkSession.user_id == user.id,
                WorkSession.start >= _utc(start, tz),
                WorkSession.start < _utc(end + timedelta(days=1), tz),
            )
            .order_by(WorkSession.start)
        ):
            d = s.start.astimezone(tz).date()
            if s.kind == PlaceKind.OFFICE:
                office_by_day.setdefault(d, places.get(s.place_id) or default_office)
            elif s.kind == PlaceKind.HOME:
                home_days.add(d)
    home_days -= set(office_by_day)

    per_office: dict[str, TaxOffice] = {}
    missing = False
    for place in office_by_day.values():
        name = place.name if place else "?"
        km = place.distance_km if place else None
        entry = per_office.setdefault(name, TaxOffice(name, km, 0, 0.0))
        entry.days += 1
        if km is None:
            missing = True
        else:
            entry.amount += commuter_allowance(km, year)
    rate, max_days = home_office_rate(year)
    counted = min(len(home_days), max_days)
    return TaxOverview(
        year=year,
        until=end,
        offices=sorted(per_office.values(), key=lambda o: -o.days),
        office_days=len(office_by_day),
        commuter_total=round(sum(o.amount for o in per_office.values()), 2),
        commuter_rate=commuter_rate(year),
        home_office_days=len(home_days),
        home_office_days_counted=counted,
        home_office_rate=rate,
        home_office_max_days=max_days,
        home_office_total=round(counted * rate, 2),
        missing_distance=missing,
    )
