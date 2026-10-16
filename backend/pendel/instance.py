"""Instance-wide settings: stored values override the PENDEL_* defaults."""

from sqlalchemy.orm import Session

from .config import get_settings
from .models import AppSetting

PUBLIC_URL = "public_url"


def get_value(db: Session, key: str) -> str | None:
    row = db.get(AppSetting, key)
    return row.value if row and row.value else None


def set_value(db: Session, key: str, value: str | None) -> None:
    row = db.get(AppSetting, key)
    if not value:
        if row:
            db.delete(row)
    elif row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))
    db.commit()


def public_url(db: Session) -> str | None:
    """External base address (e.g. Cloudflare tunnel), without trailing slash."""
    value = get_value(db, PUBLIC_URL) or get_settings().public_url
    return value.rstrip("/") if value else None
