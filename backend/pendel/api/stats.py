"""Statistics, tax overview, CSV export and the iCal feed."""

import csv
import io
from dataclasses import asdict
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select

from ..absences import periods as absence_periods
from ..auth import DB, CurrentUser, hash_token, new_token
from ..models import ApiToken, DayKind, User, utcnow
from ..reports import holiday_calendar
from ..schemas import CalendarStatus, StatsOut, TaxOut
from ..stats import aggregate, day_stats, summarize, tax_overview
from .common import FromDate, ToDate
from .records import local_range

router = APIRouter(tags=["statistics"])

CALENDAR_SCOPE = "calendar"


@router.get("/stats")
def stats(user: CurrentUser, db: DB, start: FromDate, end: ToDate, group: str = "auto") -> StatsOut:
    local_range(user, start, end)  # validates the range
    days = day_stats(db, user, start, end)
    if group not in ("week", "month"):
        group = "week" if (end - start).days <= 120 else "month"
    return StatsOut(
        start=start,
        end=end,
        group=group,
        days=[asdict(d) for d in days],
        periods=[asdict(p) for p in aggregate(days, group)],
        summary=asdict(summarize(days)),
    )


@router.get("/tax/{year}")
def tax(year: int, user: CurrentUser, db: DB) -> TaxOut:
    if not 2000 <= year <= 2100:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_year")
    return TaxOut(**asdict(tax_overview(db, user, year)))


# --- CSV ----------------------------------------------------------------------------------------

LABELS = {
    "de": {
        "head": [
            "Datum",
            "Wochentag",
            "Tagesart",
            "Ort",
            "Beginn",
            "Ende",
            "Pause",
            "Arbeitsweg",
            "Soll",
            "Ist",
            "Differenz",
            "Gleitzeitkonto",
            "Hinweise",
        ],
        "weekdays": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
        "places": {"office": "Büro", "home": "Homeoffice", "other": "Sonstiges"},
        "kinds": {
            "vacation": "Urlaub",
            "vacation_half": "Halber Urlaubstag",
            "sick": "Krank",
            "sick_child": "Kind krank",
            "flex_day": "Gleittag",
            "release": "Freistellung",
            "special_leave": "Sonderurlaub",
            "training": "Fortbildung",
            "parental_leave": "Elternzeit",
            "unpaid_leave": "Unbezahlter Urlaub",
            "public_holiday": "Feiertag",
            "workday": "Arbeitstag",
        },
        "warning": "Warnung Arbeitszeitgesetz",
    },
    "en": {
        "head": [
            "Date",
            "Weekday",
            "Day type",
            "Place",
            "Start",
            "End",
            "Break",
            "Commute",
            "Target",
            "Actual",
            "Difference",
            "Balance",
            "Notes",
        ],
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "places": {"office": "Office", "home": "Home office", "other": "Other"},
        "kinds": {k.value: k.value.replace("_", " ").capitalize() for k in DayKind},
        "warning": "Working time act warning",
    },
}


def hm(minutes: int | None, signed: bool = False) -> str:
    if minutes is None:
        return ""
    sign = ("+" if minutes > 0 else "-" if minutes < 0 else "") if signed else ("-" if minutes < 0 else "")
    m = abs(minutes)
    return f"{sign}{m // 60}:{m % 60:02d}"


@router.get("/export.csv")
def export_csv(user: CurrentUser, db: DB, start: FromDate, end: ToDate) -> Response:
    local_range(user, start, end)
    lang = LABELS["de" if user.locale == "de" else "en"]
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";" if user.locale == "de" else ",", lineterminator="\r\n")
    writer.writerow(lang["head"])
    for d in day_stats(db, user, start, end):
        kind = lang["kinds"].get(d.entry.value, "") if d.entry else (d.holiday or "")
        writer.writerow(
            [
                d.day.strftime("%d.%m.%Y" if user.locale == "de" else "%Y-%m-%d"),
                lang["weekdays"][d.day.weekday()],
                kind,
                lang["places"].get(d.place, "") if d.place else "",
                hm(d.start),
                hm(d.end),
                hm(d.breaks) if d.breaks else "",
                hm(d.commute_to + d.commute_from) if d.commute_to or d.commute_from else "",
                hm(d.target),
                hm(d.actual),
                hm(d.diff, signed=True),
                hm(d.balance, signed=True),
                lang["warning"] if d.warnings else "",
            ]
        )
    filename = f"pendel-{start.isoformat()}-{end.isoformat()}.csv"
    return Response(
        "\ufeff" + out.getvalue(),  # BOM so Excel detects UTF-8
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- iCal feed ----------------------------------------------------------------------------------


def _calendar_token(db: DB, user: User) -> ApiToken | None:
    return db.scalar(
        select(ApiToken).where(
            ApiToken.user_id == user.id, ApiToken.scope == CALENDAR_SCOPE, ApiToken.revoked_at.is_(None)
        )
    )


@router.get("/calendar")
def calendar_status(user: CurrentUser, db: DB) -> CalendarStatus:
    token = _calendar_token(db, user)
    if token is None:
        return CalendarStatus(active=False)
    return CalendarStatus(active=True, created_at=token.created_at, last_used_at=token.last_used_at)


@router.post("/calendar/token", status_code=status.HTTP_201_CREATED)
def calendar_create(user: CurrentUser, db: DB) -> CalendarStatus:
    """Create a feed URL; an existing one is revoked (new link = old link stops working)."""
    if old := _calendar_token(db, user):
        old.revoked_at = utcnow()
    token, token_hash = new_token()
    row = ApiToken(user_id=user.id, name="Kalender-Abo", token_hash=token_hash, scope=CALENDAR_SCOPE)
    db.add(row)
    db.commit()
    return CalendarStatus(active=True, created_at=row.created_at, url_path=f"/api/calendar.ics?token={token}")


@router.delete("/calendar/token", status_code=status.HTTP_204_NO_CONTENT)
def calendar_revoke(user: CurrentUser, db: DB) -> None:
    if token := _calendar_token(db, user):
        token.revoked_at = utcnow()
        db.commit()


def _ics_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545: lines longer than 75 octets continue on the next line after a space."""
    raw = line.encode()
    if len(raw) <= 75:
        return line
    parts, current = [], b""
    for ch in line:
        b = ch.encode()
        if len(current) + len(b) > (75 if not parts else 74):
            parts.append(current.decode())
            current = b""
        current += b
    parts.append(current.decode())
    return "\r\n ".join(parts)


@router.get("/calendar.ics", include_in_schema=False)
def calendar_feed(db: DB, token: str = Query(min_length=10), holidays: bool = True) -> Response:
    row = db.scalar(
        select(ApiToken).where(ApiToken.token_hash == hash_token(token), ApiToken.scope == CALENDAR_SCOPE)
    )
    if row is None or row.revoked_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    user = db.get(User, row.user_id)
    row.last_used_at = utcnow()
    db.commit()

    lang = LABELS["de" if user.locale == "de" else "en"]
    today = date.today()
    start, end = today - timedelta(days=365), today + timedelta(days=730)
    stamp = utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Pendel//Pendel//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Pendel",
        "X-PUBLISHED-TTL:PT6H",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
    ]

    def event(uid: str, first: date, last: date, summary: str, description: str = "") -> None:
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}@pendel",
                f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{first.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{(last + timedelta(days=1)).strftime('%Y%m%d')}",
                f"SUMMARY:{_ics_text(summary)}",
                "TRANSP:TRANSPARENT",
            ]
            + ([f"DESCRIPTION:{_ics_text(description)}"] if description else [])
            + ["END:VEVENT"]
        )

    for p in absence_periods(db, user, start, end):
        if p.kind == DayKind.PUBLIC_HOLIDAY and holidays:
            continue  # shown as holiday below
        label = lang["kinds"].get(p.kind.value, p.kind.value)
        event(
            f"absence-{user.id}-{p.kind.value}-{p.start.isoformat()}",
            p.start,
            p.end,
            f"{label} – {p.note}" if p.note else label,
        )
    if holidays:
        for day, name in sorted(holiday_calendar(user, range(start.year, end.year + 1)).items()):
            if start <= day <= end:
                event(f"holiday-{user.subdivision}-{day.isoformat()}", day, day, name)
    lines.append("END:VCALENDAR")
    body = "\r\n".join(_fold(line) for line in lines) + "\r\n"
    return Response(
        body,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'inline; filename="pendel.ics"', "Cache-Control": "no-cache"},
    )
