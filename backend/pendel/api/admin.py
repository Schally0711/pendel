"""Admin: invitations and user management."""

import secrets
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from starlette.background import BackgroundTask

from .. import __version__, restore
from ..auth import (
    DB,
    AdminUser,
    check_second_factor,
    disable_totp,
    end_other_sessions,
    expires_in,
    new_token,
    verify_password,
)
from ..config import get_settings
from ..db import backup_database, get_engine
from ..instance import PUBLIC_URL, public_url, set_value
from ..models import Invitation, PasswordReset, User, utcnow
from ..schemas import (
    AdminUserUpdate,
    InstanceIn,
    InstanceOut,
    InvitationCreate,
    InvitationCreated,
    InvitationOut,
    PasswordResetCreated,
    UserOut,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/invitations")
def list_invitations(_admin: AdminUser, db: DB) -> list[InvitationOut]:
    rows = db.scalars(select(Invitation).order_by(Invitation.created_at.desc()))
    return [InvitationOut.model_validate(i) for i in rows]


@router.post("/invitations", status_code=status.HTTP_201_CREATED)
def create_invitation(data: InvitationCreate, admin: AdminUser, db: DB) -> InvitationCreated:
    token, token_hash = new_token()
    inv = Invitation(
        token_hash=token_hash, note=data.note, created_by_id=admin.id, expires_at=expires_in(data.valid_days)
    )
    db.add(inv)
    db.commit()
    return InvitationCreated(**InvitationOut.model_validate(inv).model_dump(), token=token)


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invitation(invitation_id: int, _admin: AdminUser, db: DB) -> None:
    inv = db.get(Invitation, invitation_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    db.delete(inv)
    db.commit()


@router.get("/users")
def list_users(_admin: AdminUser, db: DB) -> list[UserOut]:
    return [UserOut.model_validate(u) for u in db.scalars(select(User).order_by(User.id))]


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, admin: AdminUser, db: DB) -> None:
    if user_id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot_delete_self")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    db.delete(user)
    db.commit()


@router.patch("/users/{user_id}")
def update_user(user_id: int, data: AdminUserUpdate, _admin: AdminUser, db: DB) -> UserOut:
    """Grant or revoke admin rights; there is always at least one admin."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if user.is_admin and not data.is_admin:
        admins = db.scalar(select(func.count(User.id)).where(User.is_admin)) or 0
        if admins <= 1:
            raise HTTPException(status.HTTP_409_CONFLICT, "last_admin")
    user.is_admin = data.is_admin
    db.commit()
    return UserOut.model_validate(user)


@router.delete("/users/{user_id}/totp", status_code=status.HTTP_204_NO_CONTENT)
def reset_totp(user_id: int, _admin: AdminUser, db: DB) -> None:
    """Turn off 2FA for a user who lost their device and recovery codes; ends their sessions."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    disable_totp(db, user)
    end_other_sessions(db, user, None)


RESET_LINK_HOURS = 24


@router.post("/users/{user_id}/password-reset", status_code=status.HTTP_201_CREATED)
def create_password_reset(user_id: int, admin: AdminUser, db: DB) -> PasswordResetCreated:
    """One-time link (24 h) to set a new password; earlier unused links of that user become invalid."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    for old in db.scalars(
        select(PasswordReset).where(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None))
    ):
        old.used_at = utcnow()
    token, token_hash = new_token()
    reset = PasswordReset(
        user_id=user.id,
        token_hash=token_hash,
        created_by_id=admin.id,
        expires_at=utcnow() + timedelta(hours=RESET_LINK_HOURS),
    )
    db.add(reset)
    db.commit()
    return PasswordResetCreated(token=token, expires_at=reset.expires_at)


@router.get("/backup")
def download_backup(_admin: AdminUser) -> FileResponse:
    """Consistent copy of the whole database (all users) for moving or reinstalling an instance."""
    folder = get_settings().data_dir / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / f"download-{secrets.token_hex(6)}.db"
    if backup_database(get_engine(), "download", tmp) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "restore_sqlite_only")
    name = f"pendel-backup-{utcnow():%Y-%m-%d}.db"
    return FileResponse(
        tmp,
        media_type="application/vnd.sqlite3",
        filename=name,
        background=BackgroundTask(tmp.unlink, missing_ok=True),
    )


@router.post("/restore", status_code=status.HTTP_204_NO_CONTENT)
async def restore_backup(request: Request, admin: AdminUser, db: DB) -> None:
    """Replace ALL data with an uploaded backup (raw body). Confirmed with the admin's password
    (header X-Confirm-Password, plus X-Confirm-Totp with 2FA)."""
    if not verify_password(admin.password_hash, request.headers.get("x-confirm-password", "")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "wrong_password")
    check_second_factor(db, admin, request.headers.get("x-confirm-totp"))
    db.close()
    await _restore_upload(request)


async def _restore_upload(request: Request) -> None:
    try:
        upload = await restore.receive(request.stream())
        await run_in_threadpool(restore.restore, upload)
    except restore.RestoreError as e:
        code = (
            status.HTTP_413_CONTENT_TOO_LARGE
            if str(e) == "request_too_large"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(code, str(e)) from None


@router.put("/instance")
def update_instance(data: InstanceIn, _admin: AdminUser, db: DB) -> InstanceOut:
    set_value(db, PUBLIC_URL, data.public_url)
    return InstanceOut(version=__version__, public_url=public_url(db))
