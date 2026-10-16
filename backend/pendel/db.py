import logging
import sqlite3
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


def any_users() -> bool:
    with get_engine().connect() as conn:
        return conn.exec_driver_sql("SELECT 1 FROM users LIMIT 1").first() is not None


BACKUPS_KEPT = 5


def migrate() -> None:
    """Bring the database schema up to date (runs on application startup).

    Before an existing database is changed, a consistent copy is written to
    `<data_dir>/backups/pendel-before-<version>-<timestamp>.db` (the last BACKUPS_KEPT are kept).
    """
    from alembic import command
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    engine = get_engine()
    head = ScriptDirectory.from_config(cfg).get_current_head()
    with engine.connect() as conn:
        current = MigrationContext.configure(conn).get_current_revision()
    if current is not None and current != head:
        backup_before_migration(engine)
    with migration_connection(engine) as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")


def backup_before_migration(engine: Engine) -> Path | None:
    """Copy the SQLite database with the backup API (a plain file copy would miss the WAL)."""
    if engine.dialect.name != "sqlite" or not engine.url.database:
        return None
    from datetime import UTC, datetime

    from . import __version__

    folder = Path(engine.url.database).resolve().parent / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    target = folder / f"pendel-before-{__version__}-{stamp}.db"
    source = sqlite3.connect(engine.url.database)
    dest = sqlite3.connect(target)
    try:
        source.backup(dest)
    finally:
        dest.close()
        source.close()
    for old in sorted(folder.glob("pendel-before-*.db"), key=lambda f: f.stat().st_mtime)[:-BACKUPS_KEPT]:
        old.unlink()
    logging.getLogger("uvicorn.error").warning("Database backup before migration: %s", target)
    return target
