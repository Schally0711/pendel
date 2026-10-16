"""Admin: invitations and user management."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from .. import __version__
from ..auth import DB, AdminUser, disable_totp, end_other_sessions, expires_in, new_token
from ..instance import PUBLIC_URL, public_url, set_value
from ..models import Invitation, User
from ..schemas import InstanceIn, InstanceOut, InvitationCreate, InvitationCreated, InvitationOut, UserOut

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


@router.delete("/users/{user_id}/totp", status_code=status.HTTP_204_NO_CONTENT)
def reset_totp(user_id: int, _admin: AdminUser, db: DB) -> None:
    """Turn off 2FA for a user who lost their device and recovery codes; ends their sessions."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    disable_totp(db, user)
    end_other_sessions(db, user, None)


@router.put("/instance")
def update_instance(data: InstanceIn, _admin: AdminUser, db: DB) -> InstanceOut:
    set_value(db, PUBLIC_URL, data.public_url)
    return InstanceOut(version=__version__, public_url=public_url(db))
