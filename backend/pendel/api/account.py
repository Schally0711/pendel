"""First-run setup, login/logout, own account, accepting invitations."""

import holidays
from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import func, select

from .. import __version__
from ..auth import (
    DB,
    CurrentUser,
    authenticate,
    client_key,
    end_session,
    hash_password,
    hash_token,
    login_limiter,
    normalize_email,
    start_session,
    verify_password,
)
from ..instance import public_url
from ..models import Invitation, User, utcnow
from ..schemas import (
    Credentials,
    InstanceOut,
    InvitationCheck,
    PasswordChange,
    Registration,
    SetupStatus,
    UserOut,
    UserUpdate,
)
from ..users import create_user

router = APIRouter(tags=["account"])


def _no_users(db: DB) -> bool:
    return db.scalar(select(func.count(User.id))) == 0


@router.get("/setup")
def setup_status(db: DB) -> SetupStatus:
    return SetupStatus(needed=_no_users(db))


@router.post("/setup", status_code=status.HTTP_201_CREATED)
def setup(data: Registration, request: Request, response: Response, db: DB) -> UserOut:
    """Create the first (admin) account. Only possible while no user exists."""
    if not _no_users(db):
        raise HTTPException(status.HTTP_409_CONFLICT, "already_set_up")
    user = create_user(db, data, is_admin=True)
    start_session(db, user, request, response)
    return UserOut.model_validate(user)


@router.get("/instance")
def instance(_user: CurrentUser, db: DB) -> InstanceOut:
    """Instance info for the UI (public address for links)."""
    return InstanceOut(version=__version__, public_url=public_url(db))


@router.post("/auth/login")
def login(data: Credentials, request: Request, response: Response, db: DB) -> UserOut:
    key = client_key(request)
    login_limiter.check(key)
    user = authenticate(db, data.email, data.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
    login_limiter.reset(key)
    start_session(db, user, request, response)
    return UserOut.model_validate(user)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DB) -> None:
    end_session(db, request, response)


@router.get("/me")
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me")
def update_me(data: UserUpdate, user: CurrentUser, db: DB) -> UserOut:
    if data.subdivision is not None:
        known = holidays.country_holidays(user.country).__class__.subdivisions
        if data.subdivision not in known:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unknown_subdivision")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    db.commit()
    return UserOut.model_validate(user)


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(data: PasswordChange, user: CurrentUser, db: DB) -> None:
    if not verify_password(user.password_hash, data.current_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "wrong_password")
    user.password_hash = hash_password(data.new_password)
    db.commit()


def _open_invitation(db: DB, token: str) -> Invitation | None:
    inv = db.scalar(select(Invitation).where(Invitation.token_hash == hash_token(token)))
    if inv is None or inv.used_at is not None or inv.expires_at < utcnow():
        return None
    return inv


@router.get("/invitations/{token}")
def check_invitation(token: str, db: DB) -> InvitationCheck:
    inv = _open_invitation(db, token)
    return InvitationCheck(valid=inv is not None, note=inv.note if inv else "")


@router.post("/invitations/{token}/accept", status_code=status.HTTP_201_CREATED)
def accept_invitation(
    token: str, data: Registration, request: Request, response: Response, db: DB
) -> UserOut:
    login_limiter.check(client_key(request))
    inv = _open_invitation(db, token)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invitation_invalid")
    if db.scalar(select(User).where(User.email == normalize_email(data.email))):
        raise HTTPException(status.HTTP_409_CONFLICT, "email_taken")
    user = create_user(db, data)
    inv.used_at = utcnow()
    inv.used_by_id = user.id
    db.commit()
    start_session(db, user, request, response)
    return UserOut.model_validate(user)
