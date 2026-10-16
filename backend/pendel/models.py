"""Database models.

All timestamps are stored in UTC. A work session or commute belongs to the local calendar day
(user time zone) on which it started.
"""

import enum
from datetime import UTC, date, datetime

from sqlalchemy import JSON, Boolean, Date, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .dbtypes import UTCDateTime


def utcnow() -> datetime:
    return datetime.now(UTC)


def _enum(cls: type[enum.Enum]) -> Enum:
    # Store enum values (not names) as plain strings; no DB-level enum type.
    return Enum(cls, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e])


class PlaceKind(enum.StrEnum):
    HOME = "home"
    OFFICE = "office"
    OTHER = "other"


class BreakMode(enum.StrEnum):
    MANUAL = "manual"  # only recorded breaks count
    AUTO = "auto"  # a fixed daily break is deducted; longer recorded breaks win


class DayKind(enum.StrEnum):
    VACATION = "vacation"
    VACATION_HALF = "vacation_half"
    SICK = "sick"
    FLEX_DAY = "flex_day"  # day off paid from the flexitime balance
    SPECIAL_LEAVE = "special_leave"
    PUBLIC_HOLIDAY = "public_holiday"  # manual holiday, e.g. a local one not known to the calendar
    WORKDAY = "workday"  # override: work on a day that would otherwise be a holiday


class BreakKind(enum.StrEnum):
    MANUAL = "manual"
    OFFICE_GAP = "office_gap"  # left the office and came back (detected automatically)


class CommuteDirection(enum.StrEnum):
    TO_WORK = "to_work"
    FROM_WORK = "from_work"


class Source(enum.StrEnum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"  # derived from events


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100))
    locale: Mapped[str] = mapped_column(String(8), default="de")
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Berlin")
    country: Mapped[str] = mapped_column(String(2), default="DE")
    subdivision: Mapped[str | None] = mapped_column(String(8), default="NW")  # e.g. NW = Nordrhein-Westfalen
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    work_models: Mapped[list["WorkModel"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class WorkModel(Base):
    """Contract settings, valid from a date until the next model of the same user starts."""

    __tablename__ = "work_models"
    __table_args__ = (UniqueConstraint("user_id", "valid_from"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    valid_from: Mapped[date] = mapped_column(Date)
    name: Mapped[str] = mapped_column(String(100), default="")

    # Target minutes per weekday, Monday first
    target_mon: Mapped[int] = mapped_column(Integer, default=480)
    target_tue: Mapped[int] = mapped_column(Integer, default=480)
    target_wed: Mapped[int] = mapped_column(Integer, default=480)
    target_thu: Mapped[int] = mapped_column(Integer, default=480)
    target_fri: Mapped[int] = mapped_column(Integer, default=480)
    target_sat: Mapped[int] = mapped_column(Integer, default=0)
    target_sun: Mapped[int] = mapped_column(Integer, default=0)

    flexitime: Mapped[bool] = mapped_column(Boolean, default=True)

    break_mode: Mapped[BreakMode] = mapped_column(_enum(BreakMode), default=BreakMode.MANUAL)
    auto_break_minutes: Mapped[int] = mapped_column(Integer, default=30)
    # Auto break is only deducted when the gross work time reaches this many minutes (0 = always)
    auto_break_min_work_minutes: Mapped[int] = mapped_column(Integer, default=0)
    # Warn when breaks are below the German Arbeitszeitgesetz minimum (30 min > 6 h, 45 min > 9 h)
    legal_break_check: Mapped[bool] = mapped_column(Boolean, default=True)
    # Office absences up to this length count as break; longer ones as work (e.g. customer visit)
    office_gap_break_max_minutes: Mapped[int] = mapped_column(Integer, default=90)
    # Share of commute time credited as work time
    commute_credit_percent: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped[User] = relationship(back_populates="work_models")

    def target_minutes_for_weekday(self, weekday: int) -> int:
        return (
            self.target_mon,
            self.target_tue,
            self.target_wed,
            self.target_thu,
            self.target_fri,
            self.target_sat,
            self.target_sun,
        )[weekday]


class Place(Base):
    __tablename__ = "places"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[PlaceKind] = mapped_column(_enum(PlaceKind))
    # One-way distance from home, used for the commuter allowance
    distance_km: Mapped[float | None] = mapped_column(Float)
    # Zone/geofence name an automation reports for this place (e.g. Home Assistant zone)
    zone: Mapped[str | None] = mapped_column(String(100))
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class DayEntry(Base):
    """Marks a whole day (vacation, sick, ...). Regular workdays need no entry."""

    __tablename__ = "day_entries"
    __table_args__ = (UniqueConstraint("user_id", "day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)
    kind: Mapped[DayKind] = mapped_column(_enum(DayKind))
    note: Mapped[str] = mapped_column(Text, default="")


class WorkSession(Base):
    __tablename__ = "work_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id", ondelete="SET NULL"))
    kind: Mapped[PlaceKind] = mapped_column(_enum(PlaceKind))
    start: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    end: Mapped[datetime | None] = mapped_column(UTCDateTime)  # None = running
    source: Mapped[Source] = mapped_column(_enum(Source), default=Source.MANUAL)
    note: Mapped[str] = mapped_column(Text, default="")

    breaks: Mapped[list["Break"]] = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Break.start"
    )


class Break(Base):
    __tablename__ = "breaks"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("work_sessions.id", ondelete="CASCADE"), index=True)
    start: Mapped[datetime] = mapped_column(UTCDateTime)
    end: Mapped[datetime | None] = mapped_column(UTCDateTime)  # None = running
    kind: Mapped[BreakKind] = mapped_column(_enum(BreakKind), default=BreakKind.MANUAL)
    # False = recorded absence that still counts as work time (e.g. customer visit)
    deducted: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str] = mapped_column(Text, default="")

    session: Mapped[WorkSession] = relationship(back_populates="breaks")


class Commute(Base):
    __tablename__ = "commutes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    direction: Mapped[CommuteDirection] = mapped_column(_enum(CommuteDirection))
    start: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    end: Mapped[datetime | None] = mapped_column(UTCDateTime)  # None = on the way
    from_place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id", ondelete="SET NULL"))
    to_place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id", ondelete="SET NULL"))
    source: Mapped[Source] = mapped_column(_enum(Source), default=Source.MANUAL)
    note: Mapped[str] = mapped_column(Text, default="")


class BalanceAdjustment(Base):
    """Manual change of the flexitime balance: opening balance, payout, correction."""

    __tablename__ = "balance_adjustments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    day: Mapped[date] = mapped_column(Date)
    minutes: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(Text, default="")


class Event(Base):
    """Raw event from an automation (zone enter/leave, button press). Kept for traceability."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    token_id: Mapped[int | None] = mapped_column(ForeignKey("api_tokens.id", ondelete="SET NULL"))
    type: Mapped[str] = mapped_column(String(50))  # e.g. zone_enter, zone_leave, work_start
    zone: Mapped[str | None] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)


class ApiToken(Base):
    """Token for webhooks/integrations; only the hash is stored."""

    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
