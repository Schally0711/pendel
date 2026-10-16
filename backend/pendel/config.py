from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables prefixed with PENDEL_."""

    model_config = SettingsConfigDict(env_prefix="PENDEL_", env_file=".env", extra="ignore")

    data_dir: Path = Path("./data")
    database_url: str | None = None
    # Directory with the built SvelteKit SPA; served at / when it exists.
    static_dir: Path = Path("../frontend/build")
    # Secure flag of the session cookie. Unset = automatic: secure when the request came in via
    # HTTPS (behind a proxy this needs PENDEL_FORWARDED_ALLOW_IPS so the scheme is known).
    secure_cookies: bool | None = None
    # Default for the public address (e.g. a Cloudflare tunnel); admins can override it in the UI.
    public_url: str | None = None
    # One-time code for creating the first (admin) account. Random and printed to the log on
    # startup while no user exists, unless set here (e.g. for automated installs).
    setup_token: str | None = None

    @property
    def effective_database_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'pendel.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
