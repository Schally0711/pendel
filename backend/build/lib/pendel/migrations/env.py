from alembic import context
from sqlalchemy import Connection

from pendel import models  # noqa: F401  (registers tables on Base.metadata)
from pendel.config import get_settings
from pendel.db import Base, make_engine

target_metadata = Base.metadata


def _configure(**kwargs) -> None:
    # Batch mode lets ALTER TABLE work on SQLite
    context.configure(target_metadata=target_metadata, render_as_batch=True, compare_type=True, **kwargs)


def run_migrations_offline() -> None:
    _configure(url=get_settings().effective_database_url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection: Connection | None = context.config.attributes.get("connection")
    if connection is not None:
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
        return
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    with make_engine(settings.effective_database_url).connect() as conn:
        _configure(connection=conn)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
