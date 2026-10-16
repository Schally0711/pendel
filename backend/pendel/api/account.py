"""First-run setup, login/logout, own account, accepting invitations."""

import holidays
from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select

from .. import __version__, totp
from ..auth import (
    DB,
    CurrentUser,
    check_second_factor,
    client_key,
    current_session,
    disable_totp,
    end_other_sessions,
    end_session,
    hash_password,
    hash_token,
    login,
    login_limiter,
    normalize_email,
    start_session,
    verify_password,
)
from ..instance import public_url
from ..models import Invitation, LoginSession, RecoveryCode, User, utcnow
from ..schemas import (
    Credentials,
    InstanceOut,
    InvitationCheck,
    LoginSessionOut,
    PasswordChange,
    PasswordConfirm,
    RecoveryCodes,
    Registration,
    SetupIn,
    SetupStatus,
    TotpEnable,
    TotpSetup,
    TotpStatus,
    UserOut,
    UserUpdate,
)
from ..setup import check_setup_code
from ..users import create_user

router = APIRouter(tags=["account"])


def _no_users(db: DB) -> bool:
    return db.scalar(select(func.count(User.id))) == 0


@router.get("/setup")
def setup_status(db: DB) -> SetupStatus:
    return SetupStatus(needed=_no_users(db))


@router.post("/setup", status_code=status.HTTP_201_CREATED)
def setup(data: SetupIn, request: Request, response: Response, db: DB) -> UserOut:
    """Create the first (admin) account. Only possible while no user exists, with the setup code
    from the server log."""
    if not _no_users(db):
        raise HTTPException(status.HTTP_409_CONFLICT, "already_set_up")
    login_limiter.check(client_key(request))
    if not check_setup_code(data.setup_code):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid_setup_code")
    user = create_user(db, Registration(**data.model_dump(exclude={"setup_code"})), is_admin=True)
    start_session(db, user, request, response)
    return UserOut.model_validate(user)


@router.get("/instance")
def instance(_user: CurrentUser, db: DB) -> InstanceOut:
    """Instance info for the UI (public address for links)."""
    return InstanceOut(version=__version__, public_url=public_url(db))


@router.post("/auth/login")
def login_route(data: Credentials, request: Request, response: Response, db: DB) -> UserOut:
    user = login(db, request, data.email, data.password, data.totp)
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
def change_password(data: PasswordChange, request: Request, user: CurrentUser, db: DB) -> None:
    if not verify_password(user.password_hash, data.current_password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "wrong_password")
    user.password_hash = hash_password(data.new_password)
    db.commit()
    end_other_sessions(db, user, current_session(request))


# --- login sessions ---


@router.get("/me/sessions")
def list_sessions(request: Request, user: CurrentUser, db: DB) -> list[LoginSessionOut]:
    current = current_session(request)
    rows = db.scalars(
        select(LoginSession)
        .where(LoginSession.user_id == user.id, LoginSession.expires_at > utcnow())
        .order_by(LoginSession.created_at.desc())
    )
    return [
        LoginSessionOut.model_validate(s).model_copy(
            update={"current": current is not None and s.id == current.id}
        )
        for s in rows
    ]


@router.delete("/me/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def end_login_session(session_id: int, user: CurrentUser, db: DB) -> None:
    row = db.get(LoginSession, session_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    db.delete(row)
    db.commit()


@router.delete("/me/sessions", status_code=status.HTTP_204_NO_CONTENT)
def end_all_other_sessions(request: Request, user: CurrentUser, db: DB) -> None:
    end_other_sessions(db, user, current_session(request))


# --- two-factor authentication ---


def _confirm(db: DB, user: User, data: PasswordConfirm) -> None:
    if not verify_password(user.password_hash, data.password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "wrong_password")
    check_second_factor(db, user, data.totp)


def _new_recovery_codes(db: DB, user: User) -> list[str]:
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    codes = totp.new_recovery_codes()
    db.add_all(RecoveryCode(user_id=user.id, code_hash=totp.hash_recovery_code(c)) for c in codes)
    db.commit()
    return codes


@router.get("/me/totp")
def totp_status(user: CurrentUser, db: DB) -> TotpStatus:
    left = db.scalar(
        select(func.count(RecoveryCode.id)).where(
            RecoveryCode.user_id == user.id, RecoveryCode.used_at.is_(None)
        )
    )
    return TotpStatus(enabled=user.totp_enabled, recovery_codes_left=left or 0)


@router.post("/me/totp/setup")
def totp_setup(data: PasswordConfirm, user: CurrentUser, db: DB) -> TotpSetup:
    """Start enabling 2FA: a new secret that becomes active once a code from it is confirmed."""
    if user.totp_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "totp_already_enabled")
    if not verify_password(user.password_hash, data.password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "wrong_password")
    user.totp_secret = totp.new_secret()
    db.commit()
    return TotpSetup(secret=user.totp_secret, uri=totp.provisioning_uri(user.totp_secret, user.email))


@router.post("/me/totp/enable")
def totp_enable(data: TotpEnable, request: Request, user: CurrentUser, db: DB) -> RecoveryCodes:
    if user.totp_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "totp_already_enabled")
    step = totp.verify(user.totp_secret, data.code, None) if user.totp_secret else None
    if step is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_totp")
    user.totp_enabled_at = utcnow()
    user.totp_last_step = step
    codes = _new_recovery_codes(db, user)
    end_other_sessions(db, user, current_session(request))
    return RecoveryCodes(codes=codes)


@router.post("/me/totp/disable", status_code=status.HTTP_204_NO_CONTENT)
def totp_disable(data: PasswordConfirm, user: CurrentUser, db: DB) -> None:
    if not user.totp_enabled:
        return
    _confirm(db, user, data)
    disable_totp(db, user)


@router.post("/me/totp/recovery-codes")
def totp_recovery_codes(data: PasswordConfirm, user: CurrentUser, db: DB) -> RecoveryCodes:
    if not user.totp_enabled:
        raise HTTPException(status.HTTP_409_CONFLICT, "totp_not_enabled")
    _confirm(db, user, data)
    return RecoveryCodes(codes=_new_recovery_codes(db, user))


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
