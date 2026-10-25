"""Load the exercise library into a database: free-exercise-db's exercises, then ours.

It changes rows only, never the tables: the database must have run 0002_exercise_library.sql
(`scripts/migrate.py`), or it stops. Everything runs in one transaction; without --apply it rolls
back at the end: a dry run that the database itself has checked, which changes nothing. It prints
what it added, renamed and updated, and the rows in the database that the files don't have (never
deleted). The target is the local dev database unless --database-url names
another; it's printed before anything runs.

    .venv/bin/python scripts/load_exercise_library.py
    .venv/bin/python scripts/load_exercise_library.py --apply
    .venv/bin/python scripts/load_exercise_library.py --database-url "$DATABASE_URL_STAGING"

Production only with Apoorva's approval in the same session, and a backup first.
"""
from __future__ import annotations

import argparse
import sys
from urllib.parse import urlparse

import psycopg2

from traininglogs.db.library import (
    FREE_EXERCISE_DB_COMMIT, LibraryError, load_free_exercise_db, load_library, read_free_exercise_db,
    read_library,
)

DEFAULT_URL = "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_dev"


def _print(title: str, items: list[str]) -> None:
    print(f"{title}: {len(items)}")
    for item in items:
        print(f"  {item}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=DEFAULT_URL)
    parser.add_argument("--apply", action="store_true", help="commit; without it, roll back")
    args = parser.parse_args()

    url = urlparse(args.database_url)
    print(f"Target: {url.hostname} {url.path.lstrip('/')}  ({'APPLY' if args.apply else 'dry run'})")
    print(f"free-exercise-db at commit {FREE_EXERCISE_DB_COMMIT[:7]}\n")

    conn = psycopg2.connect(args.database_url)
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('free_exercise_db') IS NOT NULL")
        if not cur.fetchone()[0]:
            print("This database hasn't run 0002_exercise_library.sql. Run scripts/migrate.py first.")
            return 1
    try:
        with conn.cursor() as cur:
            theirs = load_free_exercise_db(cur, read_free_exercise_db())
            ours = load_library(cur, read_library())
    except LibraryError as err:
        conn.rollback()
        print(f"Nothing changed. Problems:\n{err}")
        return 1
    print("free-exercise-db")
    for key in ("added", "updated", "not_in_file"):
        print(f"  {key}: {len(theirs[key])}")
    print("\nexercises")
    _print("renamed", ours["renamed"])
    _print("added", ours["added"])
    _print("updated", ours["updated"])
    _print("in the database, not in the file (left alone)", ours["not_in_file"])

    if args.apply:
        conn.commit()
        print("\nCommitted.")
    else:
        conn.rollback()
        print("\nDry run: rolled back, nothing changed. Run again with --apply to write it.")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
