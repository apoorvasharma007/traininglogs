"""Bring a database's schema up to date with the files in src/traininglogs/db/migrations/.

Dry run by default: lists the files this database hasn't run, with their SQL, and changes nothing.
--apply runs them in one transaction. The database is DATABASE_URL, which in .env is production;
for production, follow CLAUDE.md's production data rules first (a yes in the session, a backup).

    DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python scripts/migrate.py
    .venv/bin/python scripts/migrate.py --apply
"""
from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv

from traininglogs.db.db import apply_schema, get_connection, pending_migrations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="run the files (default: show them)")
    args = parser.parse_args(argv)
    load_dotenv(".env")
    host = urlparse(os.environ["DATABASE_URL"]).hostname
    conn = get_connection()
    try:
        if not args.apply:
            conn.set_session(readonly=True)
            pending = pending_migrations(conn)
            print(f"{host}: {len(pending)} file(s) to run. Nothing was changed.")
            for path in pending:
                print(f"\n-- {path.name}\n{path.read_text()}")
            return 0
        applied = apply_schema(conn)
        print(f"{host}: ran {', '.join(applied) if applied else 'nothing, already up to date'}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
