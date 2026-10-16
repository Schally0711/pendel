"""Quick actions for the "today" screen: start/stop work, breaks and commutes."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..auth import DB, CurrentUser
from ..models import Break, BreakKind, Commute, Source, User, WorkSession, utcnow
from ..reports import balance, evaluate_days
from ..schemas import BreakOut, ClockAt, ClockStart, CommuteOut, CommuteStart, SessionOut, TodayOut
from .common import conflict
from .records import check_place, running_session
from .reports import day_out

router = APIRouter(tags=["clock"])


def _at(at: datetime | None) -> datetime:
    now = utcnow()
    if at is None:
        return now
    if at > now + timedelta(minutes=5):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "time_in_future")
    return at


def _running_break(session: WorkSession | None) -> Break | None:
    if session is None:
        return None
    return next((b for b in session.breaks if b.end is None), None)


def _running_commute(db: DB, user: User) -> Commute | None:
    return db.scalar(select(Commute).where(Commute.user_id == user.id, Commute.end.is_(None)))


def _require_after(at: datetime, start: datetime) -> None:
    if at <= start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "end_before_start")


@router.get("/today")
def today(user: CurrentUser, db: DB) -> TodayOut:
    now = utcnow()
    local = now.astimezone(ZoneInfo(user.timezone)).date()
    monday = local - timedelta(days=local.weekday())
    week = evaluate_days(db, user, monday, local, now)
    session = running_session(db, user)
    brk = _running_break(session)
    commute = _running_commute(db, user)
    before = balance(db, user, local - timedelta(days=1), now)
    return TodayOut(
        now=now,
        day=day_out(week[-1]),
        running_session=SessionOut.model_validate(session) if session else None,
        running_break=BreakOut.model_validate(brk) if brk else None,
        running_commute=CommuteOut.model_validate(commute) if commute else None,
        balance=before + week[-1].result.diff,
        balance_before_today=before,
        week_actual=sum(d.result.actual for d in week),
        week_target=sum(d.result.target for d in week),
    )


@router.post("/clock/start", status_code=status.HTTP_201_CREATED)
def clock_start(data: ClockStart, user: CurrentUser, db: DB) -> SessionOut:
    if running_session(db, user):
        raise conflict("session_running")
    check_place(db, data.place_id, user)
    at = _at(data.at)
    # Arriving at work ends a running commute
    if (commute := _running_commute(db, user)) and commute.start < at:
        commute.end = at
    session = WorkSession(
        user_id=user.id, kind=data.kind, place_id=data.place_id, start=at, source=Source.MANUAL
    )
    db.add(session)
    db.commit()
    return SessionOut.model_validate(session)


@router.post("/clock/stop")
def clock_stop(data: ClockAt, user: CurrentUser, db: DB) -> SessionOut:
    session = running_session(db, user)
    if session is None:
        raise conflict("no_session_running")
    at = _at(data.at)
    _require_after(at, session.start)
    if brk := _running_break(session):
        brk.end = max(at, brk.start)
    session.end = at
    db.commit()
    return SessionOut.model_validate(session)


@router.post("/clock/break/start", status_code=status.HTTP_201_CREATED)
def break_start(data: ClockAt, user: CurrentUser, db: DB) -> BreakOut:
    session = running_session(db, user)
    if session is None:
        raise conflict("no_session_running")
    if _running_break(session):
        raise conflict("break_running")
    at = _at(data.at)
    _require_after(at, session.start)
    brk = Break(start=at, kind=BreakKind.MANUAL)
    session.breaks.append(brk)
    db.commit()
    return BreakOut.model_validate(brk)


@router.post("/clock/break/stop")
def break_stop(data: ClockAt, user: CurrentUser, db: DB) -> BreakOut:
    brk = _running_break(running_session(db, user))
    if brk is None:
        raise conflict("no_break_running")
    at = _at(data.at)
    _require_after(at, brk.start)
    brk.end = at
    db.commit()
    return BreakOut.model_validate(brk)


@router.post("/clock/commute/start", status_code=status.HTTP_201_CREATED)
def commute_start(data: CommuteStart, user: CurrentUser, db: DB) -> CommuteOut:
    if _running_commute(db, user):
        raise conflict("commute_running")
    at = _at(data.at)
    # Leaving work ends a running session
    if (session := running_session(db, user)) and session.start < at:
        if brk := _running_break(session):
            brk.end = max(at, brk.start)
        session.end = at
    commute = Commute(user_id=user.id, direction=data.direction, start=at, source=Source.MANUAL)
    db.add(commute)
    db.commit()
    return CommuteOut.model_validate(commute)


@router.post("/clock/commute/stop")
def commute_stop(data: ClockAt, user: CurrentUser, db: DB) -> CommuteOut:
    commute = _running_commute(db, user)
    if commute is None:
        raise conflict("no_commute_running")
    at = _at(data.at)
    _require_after(at, commute.start)
    commute.end = at
    db.commit()
    return CommuteOut.model_validate(commute)
