"""Turn location events (zone enter/leave) into work sessions, commutes and office breaks.

Rules (t = event time):
- leave home, workday, nothing recorded today yet → commute to work starts (a running home-office
  session ends at t)
- enter office → running commute ends, office session starts; if the session was interrupted by an
  absence from the office, that absence ends: short = break, long = work (customer visit)
- leave office during a session → absence starts (open office-gap break)
- enter home after the office → the session ends when the office was left; that time becomes the
  commute home
- enter home with a running commute to work → it was a private trip or GPS jitter: discarded

Absences shorter than GAP_JITTER_MINUTES are dropped as GPS jitter. Every result can be edited.

`device_active` ("my work laptop was opened / unlocked / joined the home network") is a smart start:
a session at the given place (default: home) starts only on a workday without absence, when nothing
is running and nothing was worked today yet – otherwise it is ignored, so triggers may fire often.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .calc import office_gap_counts_as_break, target_minutes
from .models import (
    Break,
    BreakKind,
    Commute,
    CommuteDirection,
    DayEntry,
    DayKind,
    Event,
    Place,
    PlaceKind,
    Source,
    User,
    WorkModel,
    WorkSession,
)
from .reports import holiday_calendar

GAP_JITTER_MINUTES = 3
DEFAULT_GAP_MAX_MINUTES = 90

ZONE_ENTER = "zone_enter"
ZONE_LEAVE = "zone_leave"
DEVICE_ACTIVE = "device_active"
# Day kinds on which a smart start still happens (half a vacation day means half a day of work)
WORKING_DAY_KINDS = {DayKind.WORKDAY, DayKind.VACATION_HALF}


def find_place(db: Session, user: User, zone: str | None) -> Place | None:
    """Match a reported zone against the places' zone (or name), case-insensitively.

    Accepts entity ids like "zone.arbeit" as well as names like "Arbeit".
    """
    if not zone:
        return None
    key = zone.strip().casefold().removeprefix("zone.")
    for place in db.scalars(select(Place).where(Place.user_id == user.id, Place.archived.is_(False))):
        names = {(place.zone or "").casefold().removeprefix("zone."), place.name.casefold()}
        if key in names - {""}:
            return place
    return None


def _local_day(user: User, t: datetime):
    return t.astimezone(ZoneInfo(user.timezone)).date()


def _model(db: Session, user: User, day) -> WorkModel | None:
    return db.scalar(
        select(WorkModel)
        .where(WorkModel.user_id == user.id, WorkModel.valid_from <= day)
        .order_by(WorkModel.valid_from.desc())
    )


def is_workday(db: Session, user: User, t: datetime) -> bool:
    day = _local_day(user, t)
    model = _model(db, user, day)
    if model is None:
        return False
    entry = db.scalar(select(DayEntry.kind).where(DayEntry.user_id == user.id, DayEntry.day == day))
    holiday = day in holiday_calendar(user, range(day.year, day.year + 1))
    return (
        target_minutes(model.target_minutes_for_weekday(day.weekday()), is_holiday=holiday, entry=entry) > 0
    )


def _running_session(db: Session, user: User) -> WorkSession | None:
    return db.scalar(
        select(WorkSession)
        .where(WorkSession.user_id == user.id, WorkSession.end.is_(None))
        .options(selectinload(WorkSession.breaks))
    )


def _running_commute(db: Session, user: User) -> Commute | None:
    return db.scalar(select(Commute).where(Commute.user_id == user.id, Commute.end.is_(None)))


def _open_gap(session: WorkSession) -> Break | None:
    return next((b for b in session.breaks if b.end is None and b.kind == BreakKind.OFFICE_GAP), None)


def _end_session(session: WorkSession, t: datetime) -> None:
    for b in session.breaks:
        if b.end is None:
            b.end = max(t, b.start)
    session.end = max(t, session.start)


def _gap_max(db: Session, user: User, t: datetime) -> int:
    model = _model(db, user, _local_day(user, t))
    return model.office_gap_break_max_minutes if model else DEFAULT_GAP_MAX_MINUTES


def _close_gap(db: Session, user: User, session: WorkSession, gap: Break, t: datetime) -> str:
    minutes = (t - gap.start).total_seconds() / 60
    if minutes < GAP_JITTER_MINUTES:
        session.breaks.remove(gap)
        return "gap_dropped_jitter"
    gap.end = t
    gap.deducted = office_gap_counts_as_break(minutes, _gap_max(db, user, t))
    return "gap_closed_break" if gap.deducted else "gap_closed_work"


def on_leave(db: Session, user: User, place: Place, t: datetime) -> list[str]:
    actions: list[str] = []
    session = _running_session(db, user)
    if place.kind == PlaceKind.HOME:
        if not is_workday(db, user, t):
            return ["ignored_no_workday"]
        if session and session.kind == PlaceKind.HOME:
            _end_session(session, t)
            actions.append("home_session_ended")
            session = None
        if (
            session is None
            and _running_commute(db, user) is None
            and not _worked_today_except_home(db, user, t)
        ):
            db.add(
                Commute(
                    user_id=user.id,
                    direction=CommuteDirection.TO_WORK,
                    start=t,
                    from_place_id=place.id,
                    source=Source.AUTOMATIC,
                )
            )
            actions.append("commute_to_work_started")
    elif place.kind == PlaceKind.OFFICE:
        if session and session.kind == PlaceKind.OFFICE and _open_gap(session) is None:
            session.breaks.append(Break(start=t, kind=BreakKind.OFFICE_GAP, deducted=True))
            actions.append("office_gap_started")
    return actions or ["no_change"]


def _worked_today_except_home(db: Session, user: User, t: datetime) -> bool:
    """True if an office/other session already started today (home office in the morning is fine)."""
    tz = ZoneInfo(user.timezone)
    day_start = datetime.combine(_local_day(user, t), datetime.min.time(), tz)
    count = db.scalar(
        select(func.count(WorkSession.id)).where(
            WorkSession.user_id == user.id,
            WorkSession.start >= day_start,
            WorkSession.start <= t,
            WorkSession.kind != PlaceKind.HOME,
        )
    )
    return bool(count)


def on_enter(db: Session, user: User, place: Place, t: datetime) -> list[str]:
    actions: list[str] = []
    session = _running_session(db, user)
    commute = _running_commute(db, user)
    if place.kind == PlaceKind.OFFICE:
        if session and (gap := _open_gap(session)):
            actions.append(_close_gap(db, user, session, gap, t))
        elif session is None:
            if commute and commute.direction == CommuteDirection.TO_WORK:
                commute.end = max(t, commute.start)
                commute.to_place_id = place.id
                actions.append("commute_to_work_ended")
            elif commute:  # was heading home, came back instead
                db.delete(commute)
                actions.append("commute_from_work_discarded")
            db.add(
                WorkSession(
                    user_id=user.id,
                    kind=PlaceKind.OFFICE,
                    place_id=place.id,
                    start=t,
                    source=Source.AUTOMATIC,
                )
            )
            actions.append("office_session_started")
    elif place.kind == PlaceKind.HOME:
        if session and session.kind == PlaceKind.OFFICE:
            gap = _open_gap(session)
            left = gap.start if gap else t
            if gap:
                session.breaks.remove(gap)
            else:
                session.note = (session.note + " " if session.note else "") + "[end_estimated]"
            _end_session(session, left)
            actions.append("office_session_ended")
            if gap:
                db.add(
                    Commute(
                        user_id=user.id,
                        direction=CommuteDirection.FROM_WORK,
                        start=left,
                        end=max(t, left),
                        from_place_id=session.place_id,
                        to_place_id=place.id,
                        source=Source.AUTOMATIC,
                    )
                )
                actions.append("commute_from_work_recorded")
        elif commute and commute.direction == CommuteDirection.TO_WORK:
            db.delete(commute)
            actions.append("commute_to_work_discarded")
        elif commute:
            commute.end = max(t, commute.start)
            commute.to_place_id = place.id
            actions.append("commute_from_work_ended")
    return actions or ["no_change"]


def _home_place(db: Session, user: User) -> Place | None:
    return db.scalar(
        select(Place)
        .where(Place.user_id == user.id, Place.kind == PlaceKind.HOME, Place.archived.is_(False))
        .order_by(Place.id)
    )


def on_device_active(db: Session, user: User, place: Place, t: datetime) -> list[str]:
    day = _local_day(user, t)
    entry = db.scalar(select(DayEntry.kind).where(DayEntry.user_id == user.id, DayEntry.day == day))
    if entry is not None and entry not in WORKING_DAY_KINDS:
        return ["ignored_absence"]
    if not is_workday(db, user, t):
        return ["ignored_no_workday"]
    if _running_session(db, user):
        return ["ignored_already_running"]
    if _running_commute(db, user):
        return ["ignored_commuting"]
    tz = ZoneInfo(user.timezone)
    day_start = datetime.combine(day, datetime.min.time(), tz)
    worked = db.scalar(
        select(func.count(WorkSession.id)).where(
            WorkSession.user_id == user.id, WorkSession.start >= day_start, WorkSession.start <= t
        )
    )
    if worked:
        return ["ignored_already_worked"]
    db.add(WorkSession(user_id=user.id, kind=place.kind, place_id=place.id, start=t, source=Source.AUTOMATIC))
    return ["device_session_started"]


def process(db: Session, user: User, event: Event) -> list[str]:
    """Apply one stored event; marks it processed and records the actions in its payload."""
    if event.type == DEVICE_ACTIVE:
        place = find_place(db, user, event.zone) if event.zone else _home_place(db, user)
    else:
        place = find_place(db, user, event.zone)
    if event.type == DEVICE_ACTIVE:
        actions = on_device_active(db, user, place, event.occurred_at) if place else ["ignored_unknown_zone"]
    elif event.type in (ZONE_ENTER, ZONE_LEAVE) and place is None:
        actions = ["ignored_unknown_zone"]
    elif event.type == ZONE_ENTER:
        actions = on_enter(db, user, place, event.occurred_at)
    elif event.type == ZONE_LEAVE:
        actions = on_leave(db, user, place, event.occurred_at)
    else:
        actions = ["ignored_unknown_type"]
    event.processed = True
    event.payload = {**(event.payload or {}), "actions": actions, "place_id": place.id if place else None}
    db.commit()
    return actions


def expand_zone_change(old: str | None, new: str | None) -> list[tuple[str, str]]:
    """A state change like Home Assistant's person entity ("home" → "not_home") as leave/enter events."""
    out = []
    if old and old.casefold() not in ("not_home", "unknown", "unavailable", "away"):
        out.append((ZONE_LEAVE, old))
    if new and new.casefold() not in ("not_home", "unknown", "unavailable", "away"):
        out.append((ZONE_ENTER, new))
    return out


def recent_duplicate(db: Session, user: User, type_: str, zone: str | None, t: datetime) -> bool:
    """The same event (type, zone, time) was already received, e.g. a retried webhook."""
    return bool(
        db.scalar(
            select(func.count(Event.id)).where(
                Event.user_id == user.id,
                Event.type == type_,
                Event.zone == zone,
                Event.occurred_at.between(t - timedelta(seconds=1), t + timedelta(seconds=1)),
            )
        )
    )
