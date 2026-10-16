"""Command line tools for administrators.

python -m pendel.cli create-token <email> <name> [--out FILE]
python -m pendel.cli backup [FILE]      (default: <data dir>/backups/pendel-manual-<time>.db)
"""

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import select

from .auth import new_token, normalize_email
from .db import backup_database, get_engine, get_sessionmaker, migrate
from .models import ApiToken, User


def create_token(email: str, name: str, out: str | None) -> int:
    migrate()
    with get_sessionmaker()() as db:
        user = db.scalar(select(User).where(User.email == normalize_email(email)))
        if user is None:
            print(f"no user with e-mail {email}", file=sys.stderr)
            return 1
        token, token_hash = new_token()
        db.add(ApiToken(user_id=user.id, name=name, token_hash=token_hash))
        db.commit()
    if out:
        fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(token + "\n")
        print(f"token '{name}' written to {out}")
    else:
        print(token)
    return 0


def backup(out: str | None) -> int:
    target = backup_database(get_engine(), "manual", Path(out) if out else None)
    if target is None:
        print("backups are only supported for SQLite", file=sys.stderr)
        return 1
    print(target)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pendel")
    sub = parser.add_subparsers(dest="command", required=True)
    ct = sub.add_parser("create-token", help="create an API token for a user")
    ct.add_argument("email")
    ct.add_argument("name")
    ct.add_argument("--out", help="write the token to this file (mode 600) instead of stdout")
    bk = sub.add_parser("backup", help="write a consistent copy of the database")
    bk.add_argument(
        "file", nargs="?", help="target file (default: <data dir>/backups/pendel-manual-<time>.db)"
    )
    args = parser.parse_args(argv)
    if args.command == "create-token":
        return create_token(args.email, args.name, args.out)
    if args.command == "backup":
        return backup(args.file)
    return 2


if __name__ == "__main__":
    sys.exit(main())
