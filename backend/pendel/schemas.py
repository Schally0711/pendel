"""Request and response models of the HTTP API."""

from datetime import date, datetime
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from .auth import MIN_PASSWORD_LENGTH
from .models import BreakKind, BreakMode, CommuteDirection, DayKind, PlaceKind, Source


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _check_span(start: datetime | None, end: datetime | None) -> None:
    if start is not None and end is not None and end <= start:
        raise ValueError("end must be after start")


# --- auth / users ---


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(max_length=1024)


class Registration(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+$")
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=1024)
    display_name: str = Field(min_length=1, max_length=100)
    locale: str = Field(default="de", pattern=r"^(de|en)$")


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=1024)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=1024)


class UserOut(Out):
    id: int
    email: str
    display_name: str
    locale: str
    timezone: str
    country: str
    subdivision: str | None
    is_admin: bool


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    locale: str | None = Field(default=None, pattern=r"^(de|en)$")
    timezone: str | None = Field(default=None, max_length=64)
    subdivision: str | None = Field(default=None, max_length=8)

    @field_validator("timezone")
    @classmethod
    def _valid_tz(cls, v: str | None) -> str | None:
        if v is not None:
            from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

            try:
                ZoneInfo(v)
            except (ZoneInfoNotFoundError, ValueError) as e:
                raise ValueError("unknown time zone") from e
        return v


class SetupStatus(BaseModel):
    needed: bool


class InvitationCreate(BaseModel):
    note: str = Field(default="", max_length=255)
    valid_days: int = Field(default=7, ge=1, le=90)


class InvitationOut(Out):
    id: int
    note: str
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None


class InvitationCreated(InvitationOut):
    token: str  # shown only once


class InvitationCheck(BaseModel):
    valid: bool
    note: str = ""


# --- settings ---


class PlaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: PlaceKind
    distance_km: float | None = Field(default=None, ge=0, le=1000)
    zone: str | None = Field(default=None, max_length=100)
    archived: bool = False


class PlaceOut(Out, PlaceIn):
    id: int


class WorkModelIn(BaseModel):
    valid_from: date
    name: str = Field(default="", max_length=100)
    target_mon: int = Field(default=480, ge=0, le=1440)
    target_tue: int = Field(default=480, ge=0, le=1440)
    target_wed: int = Field(default=480, ge=0, le=1440)
    target_thu: int = Field(default=480, ge=0, le=1440)
    target_fri: int = Field(default=480, ge=0, le=1440)
    target_sat: int = Field(default=0, ge=0, le=1440)
    target_sun: int = Field(default=0, ge=0, le=1440)
    flexitime: bool = True
    break_mode: BreakMode = BreakMode.MANUAL
    auto_break_minutes: int = Field(default=30, ge=0, le=480)
    auto_break_min_work_minutes: int = Field(default=0, ge=0, le=1440)
    legal_break_check: bool = True
    office_gap_break_max_minutes: int = Field(default=90, ge=0, le=1440)
    commute_credit_percent: int = Field(default=0, ge=0, le=100)


class WorkModelOut(Out, WorkModelIn):
    id: int


class AdjustmentIn(BaseModel):
    day: date
    minutes: int = Field(ge=-100_000, le=100_000)
    note: str = Field(default="", max_length=1000)


class AdjustmentOut(Out, AdjustmentIn):
    id: int


# --- records ---


class BreakIn(BaseModel):
    start: AwareDatetime
    end: AwareDatetime | None = None
    deducted: bool = True
    note: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def _span(self) -> Self:
        _check_span(self.start, self.end)
        return self


class BreakOut(Out):
    id: int
    start: datetime
    end: datetime | None
    kind: BreakKind
    deducted: bool
    note: str


class SessionIn(BaseModel):
    kind: PlaceKind
    place_id: int | None = None
    start: AwareDatetime
    end: AwareDatetime | None = None
    note: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def _span(self) -> Self:
        _check_span(self.start, self.end)
        return self


class SessionPatch(BaseModel):
    kind: PlaceKind | None = None
    place_id: int | None = None
    start: AwareDatetime | None = None
    end: AwareDatetime | None = None
    note: str | None = Field(default=None, max_length=1000)


class SessionOut(Out):
    id: int
    kind: PlaceKind
    place_id: int | None
    start: datetime
    end: datetime | None
    source: Source
    note: str
    breaks: list[BreakOut]


class CommuteIn(BaseModel):
    direction: CommuteDirection
    start: AwareDatetime
    end: AwareDatetime | None = None
    from_place_id: int | None = None
    to_place_id: int | None = None
    note: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def _span(self) -> Self:
        _check_span(self.start, self.end)
        return self


class CommuteOut(Out, CommuteIn):
    id: int
    start: datetime
    end: datetime | None
    source: Source


class DayEntryIn(BaseModel):
    kind: DayKind
    note: str = Field(default="", max_length=1000)


class DayEntryOut(Out):
    day: date
    kind: DayKind
    note: str


# --- clock (quick actions) ---


class ClockStart(BaseModel):
    kind: PlaceKind
    place_id: int | None = None
    at: AwareDatetime | None = None  # default: now


class ClockAt(BaseModel):
    at: AwareDatetime | None = None


class CommuteStart(BaseModel):
    direction: CommuteDirection
    at: AwareDatetime | None = None


# --- reports ---


class DayOut(BaseModel):
    day: date
    target: int
    actual: int
    diff: int
    gross: int
    breaks_recorded: int
    breaks_effective: int
    commute: int
    commute_credit: int
    warnings: list[str]
    holiday: str | None = None
    entry: DayKind | None = None
    kinds: list[PlaceKind] = []


class ReportOut(BaseModel):
    start: date
    end: date
    days: list[DayOut]
    target: int
    actual: int
    diff: int  # only days up to today
    balance: int  # flexitime balance at the end of the range (at most today)


class TodayOut(BaseModel):
    now: datetime
    day: DayOut
    running_session: SessionOut | None
    running_break: BreakOut | None
    running_commute: CommuteOut | None
    balance: int  # including today
    balance_before_today: int
    week_actual: int
    week_target: int


class Subdivision(BaseModel):
    code: str
    name: str


# --- absences ---


class AbsenceIn(BaseModel):
    start: date
    end: date
    kind: DayKind
    note: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def _range(self) -> Self:
        if self.end < self.start:
            raise ValueError("end must not be before start")
        if (self.end - self.start).days > 366:
            raise ValueError("range too long")
        if self.kind == DayKind.WORKDAY:
            raise ValueError("workday is not an absence")
        return self


class AbsenceResult(BaseModel):
    days: list[date]  # workdays that were (or would be) marked
    vacation_days: float


class PeriodOut(BaseModel):
    start: date
    end: date
    kind: DayKind
    note: str
    workdays: int
    vacation_days: float


class VacationAccountOut(BaseModel):
    year: int
    configured: bool
    days: float
    carried_over: float
    total: float
    taken: float
    planned: float
    remaining: float
    suggested_carry_over: float  # what was left over from the previous year


class AllowanceIn(BaseModel):
    days: float = Field(ge=0, le=366)
    carried_over: float = Field(default=0, ge=0, le=366)


class AbsencesOut(BaseModel):
    account: VacationAccountOut
    periods: list[PeriodOut]


# --- automation ---


class EventIn(BaseModel):
    """Location event from an automation.

    Either `type` zone_enter/zone_leave with `zone`, or `type` zone_change with `from`/`to`
    (e.g. Home Assistant person states like "home", "not_home", "Arbeit").
    """

    model_config = ConfigDict(populate_by_name=True)

    type: str = Field(pattern=r"^(zone_enter|zone_leave|zone_change)$")
    zone: str | None = Field(default=None, max_length=100)
    from_zone: str | None = Field(default=None, alias="from", max_length=100)
    to_zone: str | None = Field(default=None, alias="to", max_length=100)
    at: AwareDatetime | None = None
    source: str = Field(default="", max_length=50)


class EventOut(Out):
    id: int
    occurred_at: datetime
    received_at: datetime
    type: str
    zone: str | None
    payload: dict
    processed: bool


class EventResult(BaseModel):
    events: list[EventOut]


class TokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class TokenOut(Out):
    id: int
    name: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class TokenCreated(TokenOut):
    token: str  # shown only once
