"""Time-based one-time passwords (RFC 6238, as used by authenticator apps) and recovery codes."""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote, urlencode

PERIOD = 30
DIGITS = 6
WINDOW = 1  # accept the previous and next code as well (clock drift)
RECOVERY_CODES = 10


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _code(secret: str, step: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**DIGITS).zfill(DIGITS)


def code_at(secret: str, when: float) -> str:
    return _code(secret, int(when // PERIOD))


def verify(secret: str, code: str, last_step: int | None, now: float | None = None) -> int | None:
    """Return the matching time step, or None. Steps up to `last_step` are rejected (no replay)."""
    code = code.strip().replace(" ", "")
    if len(code) != DIGITS or not code.isdigit():
        return None
    current = int((time.time() if now is None else now) // PERIOD)
    for step in range(current - WINDOW, current + WINDOW + 1):
        if (last_step is None or step > last_step) and hmac.compare_digest(_code(secret, step), code):
            return step
    return None


def provisioning_uri(secret: str, account: str, issuer: str = "Pendel") -> str:
    label = f"{quote(issuer)}:{quote(account)}"
    params = urlencode({"secret": secret, "issuer": issuer, "digits": DIGITS, "period": PERIOD})
    return f"otpauth://totp/{label}?{params}"


def new_recovery_codes() -> list[str]:
    """Readable one-time codes like `k3vq-8xnm-2p`."""
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    raw = ["".join(secrets.choice(alphabet) for _ in range(10)) for _ in range(RECOVERY_CODES)]
    return [f"{c[:4]}-{c[4:8]}-{c[8:]}" for c in raw]


def normalize_recovery_code(code: str) -> str:
    return code.strip().lower().replace("-", "").replace(" ", "")


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(normalize_recovery_code(code).encode()).hexdigest()
