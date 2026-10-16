"""Password hashing, login sessions, API tokens and the FastAPI auth dependencies."""

import base64
import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import totp
from .config import get_settings
from .db import get_db
from .models import ApiToken, LoginSession, RecoveryCode, User, utcnow

SESSION_COOKIE = "pendel_session"
SESSION_LIFETIME = timedelta(days=30)
SEEN_INTERVAL = timedelta(minutes=5)  # how often a session's last activity is written
MIN_PASSWORD_LENGTH = 10

_hasher = PasswordHasher()
# Used to spend the same time on unknown e-mail addresses as on wrong passwords
_DUMMY_HASH = _hasher.hash("pendel-dummy-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def new_token() -> tuple[str, str]:
    """Return (token, sha256 hash). Tokens are random, so a fast hash is sufficient."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        verify_password(_DUMMY_HASH, password)
        return None
    if not verify_password(user.password_hash, password):
        return None
    if _hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        db.commit()
    return user


def normalize_email(email: str) -> str:
    return email.strip().lower()


def check_second_factor(db: Session, user: User, code: str | None) -> None:
    """Raise unless the user has no 2FA or `code` is a valid TOTP or unused recovery code.

    401 `totp_required` (no code given) lets the client ask for it; wrong codes are `invalid_totp`.
    """
    if user.totp_enabled_at is None or not user.totp_secret:
        return
    if not code or not code.strip():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "totp_required")
    step = totp.verify(user.totp_secret, code, user.totp_last_step)
    if step is not None:
        user.totp_last_step = step
        db.commit()
        return
    recovery = db.scalar(
        select(RecoveryCode).where(
            RecoveryCode.user_id == user.id,
            RecoveryCode.code_hash == totp.hash_recovery_code(code),
            RecoveryCode.used_at.is_(None),
        )
    )
    if recovery is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_totp")
    recovery.used_at = utcnow()
    db.commit()


def disable_totp(db: Session, user: User) -> None:
    user.totp_secret = None
    user.totp_enabled_at = None
    user.totp_last_step = None
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    db.commit()


def login(db: Session, request: Request, email: str, password: str, code: str | None) -> User:
    """Password (+ second factor) check with rate limits per client address and per account.

    The account limit only counts failures, so an attacker spreading guesses over many
    addresses is slowed down too, while the owner logging in successfully is not affected.
    """
    ip, account = client_key(request), normalize_email(email)
    login_limiter.check(ip)
    account_limiter.check(account, record=False)
    user = authenticate(db, email, password)
    if user is None:
        account_limiter.hit(account)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
    try:
        check_second_factor(db, user, code)
    except HTTPException as e:
        if e.detail == "invalid_totp":
            account_limiter.hit(account)
        raise
    login_limiter.reset(ip)
    account_limiter.reset(account)
    return user


def _secure_cookie(request: Request) -> bool:
    configured = get_settings().secure_cookies
    return request.url.scheme == "https" if configured is None else configured


def start_session(db: Session, user: User, request: Request, response: Response) -> None:
    token, token_hash = new_token()
    expires = utcnow() + SESSION_LIFETIME
    db.add(
        LoginSession(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires,
            user_agent=request.headers.get("user-agent", "")[:255],
        )
    )
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=_secure_cookie(request),
        path="/",
    )


def end_session(db: Session, request: Request, response: Response) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        session = db.scalar(select(LoginSession).where(LoginSession.token_hash == hash_token(token)))
        if session:
            db.delete(session)
            db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")


def end_other_sessions(db: Session, user: User, keep: LoginSession | None) -> None:
    """Log out everywhere else, e.g. after a password change or enabling 2FA."""
    for s in db.scalars(select(LoginSession).where(LoginSession.user_id == user.id)):
        if keep is None or s.id != keep.id:
            db.delete(s)
    db.commit()


def current_session(request: Request) -> LoginSession | None:
    """The browser session of this request (None for API tokens)."""
    return getattr(request.state, "login_session", None)


def _user_from_cookie(db: Session, request: Request) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    session = db.scalar(select(LoginSession).where(LoginSession.token_hash == hash_token(token)))
    now = utcnow()
    if session is None or session.expires_at < now:
        return None
    if session.last_seen_at is None or session.last_seen_at < now - SEEN_INTERVAL:
        session.last_seen_at = now
        db.commit()
    request.state.login_session = session
    return db.get(User, session.user_id)


def api_token(db: Session, raw: str) -> ApiToken | None:
    """Active full-scope API token for a raw token string (marks it as used)."""
    row = db.scalar(select(ApiToken).where(ApiToken.token_hash == hash_token(raw.strip())))
    if row is None or row.revoked_at is not None or row.scope != "full":
        return None
    row.last_used_at = utcnow()
    db.commit()
    return row


def _token_from_header(db: Session, request: Request) -> ApiToken | None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return api_token(db, token)


def basic_token_user(request: Request, db: Annotated[Session, Depends(get_db)]) -> User:
    """User for apps that only support HTTP Basic auth (OwnTracks): the password is an API token,
    the user name is ignored. Bearer tokens work as well."""
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    row = None
    if scheme.lower() == "basic" and value:
        try:
            _name, _, password = base64.b64decode(value.strip()).decode().partition(":")
        except (ValueError, UnicodeDecodeError):
            password = ""
        row = api_token(db, password) if password else None
    elif scheme.lower() == "bearer" and value:
        row = api_token(db, value)
    if row is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "not_authenticated",
            headers={"WWW-Authenticate": 'Basic realm="Pendel"'},
        )
    request.state.api_token = row
    user = db.get(User, row.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not_authenticated")
    return user


def current_user(request: Request, db: Annotated[Session, Depends(get_db)]) -> User:
    """Logged-in user from the session cookie or an API token (Authorization: Bearer ...)."""
    user = _user_from_cookie(db, request)
    if user is None and (api_token := _token_from_header(db, request)):
        request.state.api_token = api_token
        user = db.get(User, api_token.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not_authenticated")
    return user


def admin_user(user: Annotated[User, Depends(current_user)]) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin_required")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
BasicTokenUser = Annotated[User, Depends(basic_token_user)]
AdminUser = Annotated[User, Depends(admin_user)]
DB = Annotated[Session, Depends(get_db)]


class RateLimiter:
    """Small in-memory limiter for login attempts (per client address or per account)."""

    def __init__(self, attempts: int, window_seconds: int) -> None:
        self.attempts = attempts
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, *, record: bool = True) -> None:
        """Raise 429 when the limit is reached; otherwise count this attempt (unless record=False)."""
        now = time.monotonic()
        hits = self._hits[key]
        while hits and hits[0] < now - self.window:
            hits.popleft()
        if len(hits) >= self.attempts:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too_many_attempts")
        if record:
            hits.append(now)
        elif not hits:
            del self._hits[key]

    def hit(self, key: str) -> None:
        self._hits[key].append(time.monotonic())

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)


login_limiter = RateLimiter(attempts=10, window_seconds=15 * 60)  # attempts per client address
account_limiter = RateLimiter(attempts=20, window_seconds=60 * 60)  # failures per account


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def expires_in(days: int) -> datetime:
    return utcnow() + timedelta(days=days)
