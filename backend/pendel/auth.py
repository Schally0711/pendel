"""Password hashing, login sessions, API tokens and the FastAPI auth dependencies."""

import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import ApiToken, LoginSession, User, utcnow

SESSION_COOKIE = "pendel_session"
SESSION_LIFETIME = timedelta(days=30)
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
        secure=get_settings().secure_cookies,
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


def _user_from_cookie(db: Session, request: Request) -> User | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    session = db.scalar(select(LoginSession).where(LoginSession.token_hash == hash_token(token)))
    if session is None or session.expires_at < utcnow():
        return None
    return db.get(User, session.user_id)


def _token_from_header(db: Session, request: Request) -> ApiToken | None:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    api_token = db.scalar(select(ApiToken).where(ApiToken.token_hash == hash_token(token.strip())))
    if api_token is None or api_token.revoked_at is not None:
        return None
    api_token.last_used_at = utcnow()
    db.commit()
    return api_token


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
AdminUser = Annotated[User, Depends(admin_user)]
DB = Annotated[Session, Depends(get_db)]


class RateLimiter:
    """Small in-memory limiter for login attempts (per client address)."""

    def __init__(self, attempts: int, window_seconds: int) -> None:
        self.attempts = attempts
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and hits[0] < now - self.window:
            hits.popleft()
        if len(hits) >= self.attempts:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "too_many_attempts")
        hits.append(now)

    def reset(self, key: str) -> None:
        self._hits.pop(key, None)


login_limiter = RateLimiter(attempts=10, window_seconds=15 * 60)


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def expires_in(days: int) -> datetime:
    return utcnow() + timedelta(days=days)
