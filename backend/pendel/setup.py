"""First-run protection: the admin account can only be created with a one-time setup code.

Without it, whoever reaches a fresh instance first could claim it. The code is printed to the
log at startup (`docker logs pendel`, `journalctl -u pendel`) and changes on every restart.
"""

import hmac
import logging
import secrets

from .config import get_settings

log = logging.getLogger("uvicorn.error")
_code: str | None = None


def setup_code() -> str:
    global _code
    if _code is None:
        configured = get_settings().setup_token
        _code = configured or "-".join(secrets.token_hex(2).upper() for _ in range(3))
    return _code


def check_setup_code(code: str | None) -> bool:
    return bool(code) and hmac.compare_digest(code.strip().upper(), setup_code().upper())


def announce() -> None:
    """Log the code prominently (called on startup while no user exists)."""
    if get_settings().setup_token:
        log.warning("Pendel is not set up yet: open it in the browser and use the configured setup token.")
        return
    line = "=" * 60
    text = "Pendel is not set up yet. Open it in the browser and enter this setup code:"
    log.warning("%s\n  %s %s\n%s", line, text, setup_code(), line)


def reset() -> None:
    """Forget the code (tests)."""
    global _code
    _code = None
