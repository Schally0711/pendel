"""User creation with sensible defaults."""

from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from .auth import hash_password, normalize_email
from .models import Place, PlaceKind, User, WorkModel, utcnow
from .schemas import Registration


def create_user(db: Session, data: Registration, *, is_admin: bool = False) -> User:
    user = User(
        email=normalize_email(data.email),
        password_hash=hash_password(data.password),
        display_name=data.display_name.strip(),
        locale=data.locale,
        is_admin=is_admin,
    )
    today = utcnow().astimezone(ZoneInfo(user.timezone or "Europe/Berlin")).date()
    # Full time, 40 h/week, from the first of the current month so it can be filled in retroactively
    user.work_models.append(WorkModel(valid_from=date(today.year, today.month, 1), name="Vollzeit"))
    db.add(user)
    db.flush()
    home, office = ("Zuhause", "Büro") if data.locale == "de" else ("Home", "Office")
    db.add_all(
        [
            Place(user_id=user.id, name=home, kind=PlaceKind.HOME, zone="home"),
            Place(user_id=user.id, name=office, kind=PlaceKind.OFFICE),
        ]
    )
    db.commit()
    return user
