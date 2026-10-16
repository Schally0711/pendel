from datetime import date
from typing import Annotated

from fastapi import HTTPException, Query, status

from ..auth import DB
from ..db import Base
from ..models import User


def owned[M: Base](db: DB, model: type[M], obj_id: int, user: User) -> M:
    """Load a row of the current user or fail with 404 (also for other users' rows)."""
    obj = db.get(model, obj_id)
    if obj is None or getattr(obj, "user_id", None) != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return obj


def conflict(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, detail)


FromDate = Annotated[date, Query(alias="from")]
ToDate = Annotated[date, Query(alias="to")]
