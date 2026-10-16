"""CRUD for work sessions, breaks, commutes and day entries."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..auth import DB, CurrentUser
from ..models import Break, BreakKind, Commute, DayEntry, Place, Source, User, WorkSession
from ..schemas import (
    BreakIn,
    BreakOut,
    CommuteIn,
    CommuteOut,
    DayEntryIn,
    DayEntryOut,
    SessionIn,
    SessionOut,
    SessionPatch,
)
from .common import FromDate, ToDate, conflict, owned

router = APIRouter(tags=["records"])

MAX_RANGE_DAYS = 400


def local_range(user: User, start: date, end: date) -> tuple[datetime, datetime]:
    if end < start or (end - start).days > MAX_RANGE_DAYS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_range")
    tz = ZoneInfo(user.timezone)
    return datetime.combine(start, time.min, tz), datetime.combine(end + timedelta(days=1), time.min, tz)


def check_place(db: DB, place_id: int | None, user: User) -> None:
    if place_id is not None:
        owned(db, Place, place_id, user)


def running_session(db: DB, user: User) -> WorkSession | None:
    return db.scalar(
        select(WorkSession)
        .where(WorkSession.user_id == user.id, WorkSession.end.is_(None))
        .options(selectinload(WorkSession.breaks))
    )


def validate_breaks(session: WorkSession) -> None:
    for b in session.breaks:
        if b.start < session.start or (session.end and (b.end or b.start) > session.end):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "break_outside_session")
        if b.end is None and session.end is not None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "break_outside_session")


# --- sessions ---


@router.get("/sessions")
def list_sessions(user: CurrentUser, db: DB, start: FromDate, end: ToDate) -> list[SessionOut]:
    lo, hi = local_range(user, start, end)
    rows = db.scalars(
        select(WorkSession)
        .where(WorkSession.user_id == user.id, WorkSession.start >= lo, WorkSession.start < hi)
        .options(selectinload(WorkSession.breaks))
        .order_by(WorkSession.start)
    )
    return [SessionOut.model_validate(s) for s in rows]


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_session(data: SessionIn, user: CurrentUser, db: DB) -> SessionOut:
    check_place(db, data.place_id, user)
    if data.end is None and running_session(db, user):
        raise conflict("session_running")
    session = WorkSession(user_id=user.id, source=Source.MANUAL, **data.model_dump())
    db.add(session)
    db.commit()
    return SessionOut.model_validate(session)


@router.patch("/sessions/{session_id}")
def update_session(session_id: int, data: SessionPatch, user: CurrentUser, db: DB) -> SessionOut:
    session = owned(db, WorkSession, session_id, user)
    changes = data.model_dump(exclude_unset=True)
    if "place_id" in changes:
        check_place(db, changes["place_id"], user)
    for key, value in changes.items():
        setattr(session, key, value)
    if session.end is not None and session.end <= session.start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "end_before_start")
    validate_breaks(session)
    db.commit()
    return SessionOut.model_validate(session)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: int, user: CurrentUser, db: DB) -> None:
    db.delete(owned(db, WorkSession, session_id, user))
    db.commit()


# --- breaks ---


def _owned_break(db: DB, break_id: int, user: User) -> Break:
    brk = db.get(Break, break_id)
    if brk is None or brk.session.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return brk


@router.post("/sessions/{session_id}/breaks", status_code=status.HTTP_201_CREATED)
def create_break(session_id: int, data: BreakIn, user: CurrentUser, db: DB) -> BreakOut:
    session = owned(db, WorkSession, session_id, user)
    brk = Break(kind=BreakKind.MANUAL, **data.model_dump())
    session.breaks.append(brk)
    validate_breaks(session)
    db.commit()
    return BreakOut.model_validate(brk)


@router.put("/breaks/{break_id}")
def update_break(break_id: int, data: BreakIn, user: CurrentUser, db: DB) -> BreakOut:
    brk = _owned_break(db, break_id, user)
    for key, value in data.model_dump().items():
        setattr(brk, key, value)
    validate_breaks(brk.session)
    db.commit()
    return BreakOut.model_validate(brk)


@router.delete("/breaks/{break_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_break(break_id: int, user: CurrentUser, db: DB) -> None:
    db.delete(_owned_break(db, break_id, user))
    db.commit()


# --- commutes ---


@router.get("/commutes")
def list_commutes(user: CurrentUser, db: DB, start: FromDate, end: ToDate) -> list[CommuteOut]:
    lo, hi = local_range(user, start, end)
    rows = db.scalars(
        select(Commute)
        .where(Commute.user_id == user.id, Commute.start >= lo, Commute.start < hi)
        .order_by(Commute.start)
    )
    return [CommuteOut.model_validate(c) for c in rows]


@router.post("/commutes", status_code=status.HTTP_201_CREATED)
def create_commute(data: CommuteIn, user: CurrentUser, db: DB) -> CommuteOut:
    check_place(db, data.from_place_id, user)
    check_place(db, data.to_place_id, user)
    commute = Commute(user_id=user.id, source=Source.MANUAL, **data.model_dump())
    db.add(commute)
    db.commit()
    return CommuteOut.model_validate(commute)


@router.put("/commutes/{commute_id}")
def update_commute(commute_id: int, data: CommuteIn, user: CurrentUser, db: DB) -> CommuteOut:
    commute = owned(db, Commute, commute_id, user)
    check_place(db, data.from_place_id, user)
    check_place(db, data.to_place_id, user)
    for key, value in data.model_dump().items():
        setattr(commute, key, value)
    db.commit()
    return CommuteOut.model_validate(commute)


@router.delete("/commutes/{commute_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_commute(commute_id: int, user: CurrentUser, db: DB) -> None:
    db.delete(owned(db, Commute, commute_id, user))
    db.commit()


# --- day entries (vacation, sick, ...) ---


@router.get("/days")
def list_day_entries(user: CurrentUser, db: DB, start: FromDate, end: ToDate) -> list[DayEntryOut]:
    rows = db.scalars(
        select(DayEntry)
        .where(DayEntry.user_id == user.id, DayEntry.day.between(start, end))
        .order_by(DayEntry.day)
    )
    return [DayEntryOut.model_validate(e) for e in rows]


@router.put("/days/{day}")
def set_day_entry(day: date, data: DayEntryIn, user: CurrentUser, db: DB) -> DayEntryOut:
    entry = db.scalar(select(DayEntry).where(DayEntry.user_id == user.id, DayEntry.day == day))
    if entry is None:
        entry = DayEntry(user_id=user.id, day=day)
        db.add(entry)
    entry.kind = data.kind
    entry.note = data.note
    db.commit()
    return DayEntryOut.model_validate(entry)


@router.delete("/days/{day}", status_code=status.HTTP_204_NO_CONTENT)
def delete_day_entry(day: date, user: CurrentUser, db: DB) -> None:
    entry = db.scalar(select(DayEntry).where(DayEntry.user_id == user.id, DayEntry.day == day))
    if entry is not None:
        db.delete(entry)
        db.commit()
