"""Absence periods and vacation account."""

from datetime import date

from fastapi import APIRouter, HTTPException, Query, status

from ..absences import account_employment, delete_range, periods, set_allowance, set_range, vacation_account
from ..auth import DB, CurrentUser
from ..models import VACATION_DAYS, User
from ..schemas import AbsenceIn, AbsenceResult, AbsencesOut, AllowanceIn, PeriodOut, VacationAccountOut
from .common import FromDate, ToDate

router = APIRouter(tags=["absences"])


def _account(db: DB, user: User, year: int) -> VacationAccountOut:
    acc = vacation_account(db, user, year)
    emp = acc.employment
    # Carry-over only within the same employment
    same = emp is None or account_employment(db, user, year - 1) is emp
    prev = vacation_account(db, user, year - 1, emp) if same else None
    return VacationAccountOut(
        year=acc.year,
        employment_id=emp.id if emp else None,
        employer=emp.employer if emp else "",
        configured=acc.configured,
        days=acc.days,
        carried_over=acc.carried_over,
        total=acc.total,
        taken=acc.taken,
        planned=acc.planned,
        remaining=acc.remaining,
        suggested_carry_over=max(prev.remaining, 0) if prev and prev.configured else 0,
    )


@router.get("/absences")
def list_absences(user: CurrentUser, db: DB, year: int = Query(ge=2000, le=2100)) -> AbsencesOut:
    found = periods(db, user, date(year, 1, 1), date(year, 12, 31))
    return AbsencesOut(
        account=_account(db, user, year),
        periods=[PeriodOut(**p.__dict__) for p in found],
    )


@router.post("/absences")
def add_absence(data: AbsenceIn, user: CurrentUser, db: DB, dry_run: bool = False) -> AbsenceResult:
    days = set_range(db, user, data.start, data.end, data.kind, data.note, dry_run=dry_run)
    return AbsenceResult(days=days, vacation_days=len(days) * VACATION_DAYS.get(data.kind, 0.0))


@router.delete("/absences", status_code=status.HTTP_204_NO_CONTENT)
def remove_absences(user: CurrentUser, db: DB, start: FromDate, end: ToDate) -> None:
    if end < start or (end - start).days > 366:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_range")
    delete_range(db, user, start, end)


@router.get("/vacation/{year}")
def get_vacation(year: int, user: CurrentUser, db: DB) -> VacationAccountOut:
    return _account(db, user, year)


@router.put("/vacation/{year}")
def put_vacation(year: int, data: AllowanceIn, user: CurrentUser, db: DB) -> VacationAccountOut:
    if not 2000 <= year <= 2100:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_year")
    set_allowance(db, user, year, data.days, data.carried_over)
    return _account(db, user, year)
