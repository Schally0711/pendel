"""Pure time accounting rules (no database access).

Everything is in minutes. Running intervals (no end yet) are evaluated up to `now`.
"""

from dataclasses import dataclass, field
from datetime import date, datetime

from .models import NEUTRAL_DAY_KINDS, BreakMode, DayKind

# German Arbeitszeitgesetz §4: required break by working time (without breaks)
LEGAL_BREAKS = ((9 * 60, 45), (6 * 60, 30))
LEGAL_MAX_WORK_MINUTES = 10 * 60

WARN_BREAK_TOO_SHORT = "break_too_short"
WARN_MAX_WORK_EXCEEDED = "max_work_exceeded"


@dataclass(frozen=True)
class Span:
    start: datetime
    end: datetime | None = None

    def minutes(self, now: datetime) -> float:
        end = self.end or now
        return max((end - self.start).total_seconds() / 60, 0.0)


@dataclass(frozen=True)
class BreakSpan(Span):
    deducted: bool = True


@dataclass(frozen=True)
class SessionSpan(Span):
    breaks: tuple[BreakSpan, ...] = ()


@dataclass(frozen=True)
class Rules:
    break_mode: BreakMode = BreakMode.MANUAL
    auto_break_minutes: int = 30
    auto_break_min_work_minutes: int = 0
    legal_break_check: bool = True
    commute_credit_percent: int = 0


@dataclass
class DayResult:
    day: date
    target: int
    gross: int  # time between session start and end, breaks included
    breaks_recorded: int  # recorded breaks that count as break
    breaks_effective: int  # what is actually deducted (incl. automatic break)
    commute: int
    commute_credit: int
    actual: int  # credited work time
    warnings: list[str] = field(default_factory=list)

    @property
    def diff(self) -> int:
        return self.actual - self.target


def target_minutes(base: int, *, is_holiday: bool, entry: DayKind | None) -> int:
    """Target time of a day.

    `base` is the weekday target of the active work model. Absences like vacation, sickness,
    release or training and holidays are neutral (target 0); a flex day keeps the target so it is
    paid from the balance.
    """
    if entry == DayKind.WORKDAY:
        return base
    if entry in NEUTRAL_DAY_KINDS:
        return 0
    if entry == DayKind.VACATION_HALF:
        return 0 if is_holiday else round(base / 2)
    return 0 if is_holiday else base


def office_gap_counts_as_break(gap_minutes: float, max_break_minutes: int) -> bool:
    """Leaving the office and coming back: short gaps are breaks, long ones e.g. customer visits."""
    return gap_minutes <= max_break_minutes


def required_break(work_minutes: float) -> int:
    for threshold, minutes in LEGAL_BREAKS:
        if work_minutes > threshold:
            return minutes
    return 0


def evaluate_day(
    day: date,
    target: int,
    sessions: list[SessionSpan],
    commutes: list[Span],
    rules: Rules,
    now: datetime,
) -> DayResult:
    gross = sum(s.minutes(now) for s in sessions)
    recorded = sum(min(b.minutes(now), s.minutes(now)) for s in sessions for b in s.breaks if b.deducted)

    effective = recorded
    if rules.break_mode == BreakMode.AUTO and sessions and gross >= rules.auto_break_min_work_minutes:
        effective = max(recorded, rules.auto_break_minutes)
    effective = min(effective, gross)

    commute = sum(c.minutes(now) for c in commutes)
    commute_credit = commute * rules.commute_credit_percent / 100
    work = gross - effective

    warnings = []
    if rules.legal_break_check and sessions:
        if effective < required_break(work):
            warnings.append(WARN_BREAK_TOO_SHORT)
        if work + commute_credit > LEGAL_MAX_WORK_MINUTES:
            warnings.append(WARN_MAX_WORK_EXCEEDED)

    return DayResult(
        day=day,
        target=target,
        gross=round(gross),
        breaks_recorded=round(recorded),
        breaks_effective=round(effective),
        commute=round(commute),
        commute_credit=round(commute_credit),
        actual=round(work + commute_credit),
        warnings=warnings,
    )
