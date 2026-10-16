"""API tokens and the event webhooks for automations (Home Assistant, OwnTracks, Shortcuts, Tasker, ...)."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Request, status
from sqlalchemy import select

from ..auth import DB, BasicTokenUser, CurrentUser, login, new_token
from ..automation import ZONE_ENTER, ZONE_LEAVE, expand_zone_change, process, recent_duplicate
from ..models import ApiToken, Event, User, utcnow
from ..schemas import EventIn, EventOut, EventResult, TokenCreate, TokenCreated, TokenLogin, TokenOut
from .common import FromDate, ToDate, owned
from .records import local_range

router = APIRouter(tags=["integrations"])

MAX_EVENT_AGE = timedelta(days=7)


@router.post("/events")
def receive_event(data: EventIn, request: Request, user: CurrentUser, db: DB) -> EventResult:
    now = utcnow()
    at = data.at or now
    if at > now + timedelta(minutes=5) or at < now - MAX_EVENT_AGE:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "event_time_out_of_range")
    if data.type == "zone_change":
        parts = expand_zone_change(data.from_zone, data.to_zone)
    else:
        if not data.zone:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "zone_missing")
        parts = [(ZONE_ENTER if data.type == ZONE_ENTER else ZONE_LEAVE, data.zone)]

    return EventResult(events=_record(db, user, request, parts, at, data.source))


def _record(
    db: DB, user: User, request: Request, parts: list[tuple[str, str]], at: datetime, source: str
) -> list[EventOut]:
    """Store zone events (skipping duplicates) and run them through the automation rules."""
    token = getattr(request.state, "api_token", None)
    out = []
    for type_, zone in parts:
        if recent_duplicate(db, user, type_, zone, at):
            continue
        event = Event(
            user_id=user.id,
            occurred_at=at,
            type=type_,
            zone=zone,
            token_id=token.id if token else None,
            payload={"source": source} if source else {},
        )
        db.add(event)
        db.flush()
        process(db, user, event)
        out.append(EventOut.model_validate(event))
    return out


@router.post("/owntracks")
def owntracks(request: Request, user: BasicTokenUser, db: DB, msg: Annotated[Any, Body()] = None) -> list:
    """OwnTracks HTTP mode. Only region transitions are used; location fixes and all other
    message types are acknowledged and dropped (no coordinates are stored).

    OwnTracks expects `200` with a JSON array; anything else makes it retry, so old or
    unusable messages are acknowledged too.
    """
    if not isinstance(msg, dict) or msg.get("_type") != "transition":
        return []
    event, region, tst = msg.get("event"), msg.get("desc"), msg.get("tst")
    if event not in ("enter", "leave") or not isinstance(region, str) or not region.strip():
        return []
    now = utcnow()
    try:
        at = datetime.fromtimestamp(float(tst), UTC) if tst is not None else now
    except (TypeError, ValueError, OverflowError):
        at = now
    if at > now + timedelta(minutes=5) or at < now - MAX_EVENT_AGE:
        return []
    type_ = ZONE_ENTER if event == "enter" else ZONE_LEAVE
    _record(db, user, request, [(type_, region.strip()[:100])], at, "owntracks")
    return []


@router.get("/events")
def list_events(user: CurrentUser, db: DB, start: FromDate, end: ToDate) -> list[EventOut]:
    lo, hi = local_range(user, start, end)
    rows = db.scalars(
        select(Event)
        .where(Event.user_id == user.id, Event.occurred_at >= lo, Event.occurred_at < hi)
        .order_by(Event.occurred_at, Event.id)
    )
    return [EventOut.model_validate(e) for e in rows]


@router.get("/tokens")
def list_tokens(user: CurrentUser, db: DB) -> list[TokenOut]:
    rows = db.scalars(select(ApiToken).where(ApiToken.user_id == user.id).order_by(ApiToken.created_at))
    return [TokenOut.model_validate(t) for t in rows]


@router.post("/tokens", status_code=status.HTTP_201_CREATED)
def create_token(data: TokenCreate, user: CurrentUser, db: DB) -> TokenCreated:
    token, token_hash = new_token()
    row = ApiToken(user_id=user.id, name=data.name.strip(), token_hash=token_hash)
    db.add(row)
    db.commit()
    return TokenCreated(**TokenOut.model_validate(row).model_dump(), token=token)


@router.post("/auth/token", status_code=status.HTTP_201_CREATED)
def login_for_token(data: TokenLogin, request: Request, db: DB) -> TokenCreated:
    """Create an API token with e-mail and password, e.g. from the Home Assistant setup dialog."""
    user = login(db, request, data.email, data.password, data.totp)
    token, token_hash = new_token()
    row = ApiToken(user_id=user.id, name=data.name.strip(), token_hash=token_hash)
    db.add(row)
    db.commit()
    return TokenCreated(**TokenOut.model_validate(row).model_dump(), token=token)


@router.delete("/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(token_id: int, user: CurrentUser, db: DB) -> None:
    row = owned(db, ApiToken, token_id, user)
    if row.revoked_at is None:
        row.revoked_at = utcnow()
        db.commit()
