from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(conn, _record):
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

    return engine


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return make_engine(settings.effective_database_url)


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a database session."""
    with get_sessionmaker()() as session:
        yield session


@contextmanager
def migration_connection(engine: Engine) -> Iterator[Connection]:
    """Connection for schema migrations with foreign keys switched off.

    Batch migrations rebuild SQLite tables (copy, drop, rename); with foreign keys on, dropping
    a parent table would cascade-delete its children. The pragma only works outside a transaction.
    """
    with engine.connect() as conn:
        sqlite = engine.dialect.name == "sqlite"
        if sqlite:
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
            conn.commit()
        try:
            with conn.begin():
                yield conn
                if sqlite and (bad := conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall()):
                    raise RuntimeError(f"foreign key violations after migration: {bad[:5]}")
        finally:
            if sqlite:
                conn.exec_driver_sql("PRAGMA foreign_keys=ON")
                conn.commit()


def migrate() -> None:
    """Bring the database schema up to date (runs on application startup)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    with migration_connection(get_engine()) as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
