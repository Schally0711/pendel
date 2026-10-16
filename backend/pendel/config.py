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

    @property
    def effective_database_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'pendel.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
