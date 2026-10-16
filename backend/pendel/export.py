"""Personal data export: everything Pendel stores about one user, as a JSON document."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import __version__
from .models import (
    ApiToken,
    BalanceAdjustment,
    Commute,
    DayEntry,
    Employment,
    Event,
    LoginSession,
    Place,
    User,
    VacationAllowance,
    WorkModel,
    WorkSession,
    utcnow,
)

# Never part of an export: credentials and secrets
SECRET_COLUMNS = {"password_hash", "token_hash", "totp_secret", "totp_last_step", "code_hash"}


def _row(obj: Any, skip: set[str] = frozenset()) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for col in obj.__table__.columns:
        if col.key in SECRET_COLUMNS or col.key in skip:
            continue
        value = getattr(obj, col.key)
        if isinstance(value, datetime | date):
            value = value.isoformat()
        elif hasattr(value, "value"):  # enums
            value = value.value
        out[col.key] = value
    return out


def user_export(db: Session, user: User) -> dict[str, Any]:
    def rows(model, order) -> list[dict[str, Any]]:
        query = select(model).where(model.user_id == user.id).order_by(order)
        return [_row(r, {"user_id"}) for r in db.scalars(query)]

    sessions = []
    for s in db.scalars(
        select(WorkSession)
        .where(WorkSession.user_id == user.id)
        .order_by(WorkSession.start)
        .options(selectinload(WorkSession.breaks))
    ):
        item = _row(s, {"user_id"})
        item["breaks"] = [_row(b, {"session_id"}) for b in sorted(s.breaks, key=lambda b: b.start)]
        sessions.append(item)

    return {
        "format": "pendel-user-export",
        "format_version": 1,
        "pendel_version": __version__,
        "exported_at": utcnow().isoformat(),
        "user": {**_row(user), "totp_enabled": user.totp_enabled},
        "employments": rows(Employment, Employment.start),
        "work_models": rows(WorkModel, WorkModel.valid_from),
        "places": rows(Place, Place.id),
        "vacation_allowances": rows(VacationAllowance, VacationAllowance.year),
        "balance_adjustments": rows(BalanceAdjustment, BalanceAdjustment.day),
        "day_entries": rows(DayEntry, DayEntry.day),
        "work_sessions": sessions,
        "commutes": rows(Commute, Commute.start),
        "events": rows(Event, Event.occurred_at),
        "api_tokens": rows(ApiToken, ApiToken.created_at),
        "login_sessions": rows(LoginSession, LoginSession.created_at),
    }
