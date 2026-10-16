"""Per-user settings: places, work models, balance adjustments."""

import holidays
from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..auth import DB, CurrentUser
from ..models import BalanceAdjustment, Place, WorkModel
from ..schemas import (
    AdjustmentIn,
    AdjustmentOut,
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
