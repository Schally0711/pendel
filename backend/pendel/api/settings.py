"""Per-user settings: places, work models, employments, balance adjustments."""

import holidays
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..auth import DB, CurrentUser
from ..employments import EmploymentError, delete_with_data, employment_on, employments, switch, validate
from ..models import BalanceAdjustment, Employment, Place, User, WorkModel
from ..reports import balance, local_today
from ..schemas import (
    AdjustmentIn,
    AdjustmentOut,
    EmploymentIn,
    EmploymentOut,
    EmploymentSwitch,
    PlaceIn,
    PlaceOut,
    Subdivision,
    WorkModelIn,
    WorkModelOut,
)
from .common import conflict, owned

router = APIRouter(tags=["settings"])


@router.get("/meta/subdivisions")
def subdivisions(user: CurrentUser) -> list[Subdivision]:
    cls = holidays.country_holidays(user.country).__class__
    names = getattr(cls, "subdivisions_aliases", {})
    by_code = {code: alias for alias, code in names.items()}
    return [Subdivision(code=c, name=by_code.get(c, c)) for c in cls.subdivisions]


# --- places ---


@router.get("/places")
def list_places(user: CurrentUser, db: DB) -> list[PlaceOut]:
    rows = db.scalars(select(Place).where(Place.user_id == user.id).order_by(Place.id))
    return [PlaceOut.model_validate(p) for p in rows]


@router.post("/places", status_code=status.HTTP_201_CREATED)
def create_place(data: PlaceIn, user: CurrentUser, db: DB) -> PlaceOut:
    place = Place(user_id=user.id, **data.model_dump())
    db.add(place)
    db.commit()
    return PlaceOut.model_validate(place)


@router.put("/places/{place_id}")
def update_place(place_id: int, data: PlaceIn, user: CurrentUser, db: DB) -> PlaceOut:
    place = owned(db, Place, place_id, user)
    for key, value in data.model_dump().items():
        setattr(place, key, value)
    db.commit()
    return PlaceOut.model_validate(place)


@router.delete("/places/{place_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_place(place_id: int, user: CurrentUser, db: DB) -> None:
    db.delete(owned(db, Place, place_id, user))
    db.commit()


# --- work models ---


@router.get("/work-models")
def list_work_models(user: CurrentUser, db: DB) -> list[WorkModelOut]:
    rows = db.scalars(select(WorkModel).where(WorkModel.user_id == user.id).order_by(WorkModel.valid_from))
    return [WorkModelOut.model_validate(m) for m in rows]


def _save_model(db: DB, model: WorkModel) -> WorkModelOut:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise conflict("valid_from_taken") from None
    return WorkModelOut.model_validate(model)


@router.post("/work-models", status_code=status.HTTP_201_CREATED)
def create_work_model(data: WorkModelIn, user: CurrentUser, db: DB) -> WorkModelOut:
    model = WorkModel(user_id=user.id, **data.model_dump())
    db.add(model)
    return _save_model(db, model)


@router.put("/work-models/{model_id}")
def update_work_model(model_id: int, data: WorkModelIn, user: CurrentUser, db: DB) -> WorkModelOut:
    model = owned(db, WorkModel, model_id, user)
    for key, value in data.model_dump().items():
        setattr(model, key, value)
    return _save_model(db, model)


@router.delete("/work-models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_model(model_id: int, user: CurrentUser, db: DB) -> None:
    model = owned(db, WorkModel, model_id, user)
    count = len(list(db.scalars(select(WorkModel.id).where(WorkModel.user_id == user.id))))
    if count == 1:
        raise conflict("last_work_model")
    db.delete(model)
    db.commit()


# --- employments ---


def _employment_out(db: DB, user: User, emp: Employment) -> EmploymentOut:
    today = local_today(user)
    out = EmploymentOut.model_validate(emp)
    out.current = employment_on([emp], today) is not None
    out.balance = balance(db, user, min(emp.end or today, today)) if emp.start <= today else 0
    return out


def _bad(e: EmploymentError) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.get("/employments")
def list_employments(user: CurrentUser, db: DB) -> list[EmploymentOut]:
    return [_employment_out(db, user, e) for e in employments(db, user)]


@router.put("/employments/{employment_id}")
def update_employment(employment_id: int, data: EmploymentIn, user: CurrentUser, db: DB) -> EmploymentOut:
    emp = owned(db, Employment, employment_id, user)
    for key, value in data.model_dump().items():
        setattr(emp, key, value)
    try:
        validate(employments(db, user))
    except EmploymentError as e:
        db.rollback()
        raise _bad(e) from None
    db.commit()
    return _employment_out(db, user, emp)


@router.post("/employments/switch", status_code=status.HTTP_201_CREATED)
def switch_employment(data: EmploymentSwitch, user: CurrentUser, db: DB) -> EmploymentOut:
    try:
        emp = switch(db, user, **data.model_dump())
    except EmploymentError as e:
        db.rollback()
        raise _bad(e) from None
    return _employment_out(db, user, emp)


@router.delete("/employments/{employment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employment(employment_id: int, user: CurrentUser, db: DB) -> None:
    """Delete an ended employment together with all data recorded within it."""
    try:
        delete_with_data(db, user, owned(db, Employment, employment_id, user))
    except EmploymentError as e:
        db.rollback()
        raise _bad(e) from None


# --- balance adjustments ---


@router.get("/adjustments")
def list_adjustments(user: CurrentUser, db: DB) -> list[AdjustmentOut]:
    rows = db.scalars(
        select(BalanceAdjustment).where(BalanceAdjustment.user_id == user.id).order_by(BalanceAdjustment.day)
    )
    return [AdjustmentOut.model_validate(a) for a in rows]


@router.post("/adjustments", status_code=status.HTTP_201_CREATED)
def create_adjustment(data: AdjustmentIn, user: CurrentUser, db: DB) -> AdjustmentOut:
    adj = BalanceAdjustment(user_id=user.id, **data.model_dump())
    db.add(adj)
    db.commit()
    return AdjustmentOut.model_validate(adj)


@router.put("/adjustments/{adj_id}")
def update_adjustment(adj_id: int, data: AdjustmentIn, user: CurrentUser, db: DB) -> AdjustmentOut:
    adj = owned(db, BalanceAdjustment, adj_id, user)
    for key, value in data.model_dump().items():
        setattr(adj, key, value)
    db.commit()
    return AdjustmentOut.model_validate(adj)


@router.delete("/adjustments/{adj_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_adjustment(adj_id: int, user: CurrentUser, db: DB) -> None:
    db.delete(owned(db, BalanceAdjustment, adj_id, user))
    db.commit()
