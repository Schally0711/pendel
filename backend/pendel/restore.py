"""Instance backup download and restore (the whole SQLite database).

A restore validates the uploaded file first (SQLite, integrity, a Pendel schema revision this version
knows), backs up the current database, swaps the file in and migrates it to the current schema –
so a backup from an older Pendel version can be restored into a newer one.
"""

import os
import secrets
import sqlite3
from collections.abc import AsyncIterator
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from .db import backup_database, get_engine, migrate

MAX_UPLOAD_BYTES = 512 * 1024 * 1024


class RestoreError(ValueError):
    """Unusable backup; the message is an API error code."""


def _database_path() -> Path:
    engine = get_engine()
    if engine.dialect.name != "sqlite" or not engine.url.database:
        raise RestoreError("restore_sqlite_only")
    return Path(engine.url.database).resolve()


def _known_revisions() -> set[str]:
    cfg = Config()
    cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    return {rev.revision for rev in ScriptDirectory.from_config(cfg).walk_revisions()}


def validate(path: Path) -> None:
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            if conn.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise RestoreError("backup_damaged")
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            if not {"alembic_version", "users"} <= tables:
                raise RestoreError("backup_not_pendel")
            (revision,) = conn.execute("SELECT version_num FROM alembic_version").fetchone() or (None,)
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        raise RestoreError("backup_not_pendel") from None
    if revision not in _known_revisions():
        raise RestoreError("backup_too_new")


async def receive(chunks: AsyncIterator[bytes]) -> Path:
    """Write an uploaded file next to the database (same file system for the final rename)."""
    folder = _database_path().parent / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"upload-{secrets.token_hex(6)}.db"
    size = 0
    try:
        with target.open("wb") as f:
            async for chunk in chunks:
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise RestoreError("request_too_large")
                f.write(chunk)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    if size == 0:
        target.unlink(missing_ok=True)
        raise RestoreError("backup_not_pendel")
    return target


def restore(upload: Path) -> None:
    """Replace the database with a validated upload (the upload file is consumed)."""
    try:
        validate(upload)
        db_path = _database_path()
        engine = get_engine()
        if db_path.exists():
            backup_database(engine, "before-restore")
        engine.dispose()
        staged = db_path.with_name(db_path.name + ".restore")
        src, dst = sqlite3.connect(upload), sqlite3.connect(staged)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        for suffix in ("-wal", "-shm"):
            Path(str(db_path) + suffix).unlink(missing_ok=True)
        os.replace(staged, db_path)
        engine.dispose()
        migrate()
    finally:
        upload.unlink(missing_ok=True)
