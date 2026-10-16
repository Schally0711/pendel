"""Evaluated days and flexitime balance."""

from fastapi import APIRouter

from ..auth import DB, CurrentUser
from ..reports import DayReport, balance, evaluate_days
from ..schemas import DayOut, ReportOut
from .common import FromDate, ToDate
from .records import local_range

router = APIRouter(tags=["reports"])


def day_out(d: DayReport) -> DayOut:
    r = d.result
    return DayOut(
        day=r.day,
        target=r.target,
        actual=r.actual,
        diff=r.diff,
        gross=r.gross,
        breaks_recorded=r.breaks_recorded,
        breaks_effective=r.breaks_effective,
        commute=r.commute,
        commute_credit=r.commute_credit,
        warnings=r.warnings,
        holiday=d.holiday,
        entry=d.entry,
        kinds=d.kinds,
    )


@router.get("/report")
def report(user: CurrentUser, db: DB, start: FromDate, end: ToDate) -> ReportOut:
    local_range(user, start, end)  # validates the range
    days = evaluate_days(db, user, start, end)
    return ReportOut(
        start=start,
        end=end,
        days=[day_out(d) for d in days],
        target=sum(d.result.target for d in days),
        actual=sum(d.result.actual for d in days),
        diff=sum(d.result.diff for d in days),
        balance=balance(db, user, end),
    )
