"""Copy production into the local dev database or staging, to try the app on real data.

Reads production (DATABASE_URL) in a read-only transaction and never writes to it. Applies
schema.sql to the target, empties every table, and copies them all in. The target is
DEV_DATABASE_URL: the `traininglogs_dev` database in the local Docker Postgres by default, or
staging's (DATABASE_URL_STAGING); anything else is refused. Run it again any time to start fresh.

In staging, each person signs in with a different Supabase account id than in production, so
each copied user is pointed at the staging account with the same email. Someone who hasn't signed
into staging yet keeps production's id until the next copy.

    .venv/bin/python scripts/copy_prod_to_dev.py
    DEV_DATABASE_URL="$DATABASE_URL_STAGING" .venv/bin/python scripts/copy_prod_to_dev.py
"""
from __future__ import annotations

import io
import os
import sys
from urllib.parse import urlparse

import psycopg2
from dotenv import load_dotenv

from traininglogs.db.db import apply_schema

DEFAULT_DEV_URL = "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_dev"

# Parents before children, so links hold while copying.
TABLES = [
    "users", "profiles", "exercises", "user_exercises", "input_text", "input_text_confirmation_cards",
    "ai_call_logs", "programs", "program_workouts", "program_workout_exercises", "workout_sessions",
    "workout_session_warmups", "workout_session_cooldowns", "workout_session_exercises", "workout_session_sets",
]


def _columns(cur, table: str) -> list[str]:
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s"
        " AND is_generated = 'NEVER' ORDER BY ordinal_position",
        (table,),
    )
    return [r[0] for r in cur.fetchall()]


def main() -> int:
    load_dotenv(".env")
    prod_url = os.environ["DATABASE_URL"]
    target_url = os.environ.get("DEV_DATABASE_URL", DEFAULT_DEV_URL)
    local = urlparse(target_url).hostname in ("localhost", "127.0.0.1")
    if not (local or target_url == os.environ.get("DATABASE_URL_STAGING")) or target_url == prod_url:
        print(f"Refusing: the target must be on this machine or be staging, got {urlparse(target_url).hostname}")
        return 1

    prod = psycopg2.connect(prod_url)
    prod.set_session(readonly=True)
    target = psycopg2.connect(target_url)
    apply_schema(target)

    with prod.cursor() as p, target.cursor() as t:
        t.execute(f"TRUNCATE {', '.join(TABLES)} CASCADE")
        for table in TABLES:
            cols = ", ".join(f'"{c}"' for c in _columns(t, table))
            buf = io.StringIO()
            p.copy_expert(f"COPY (SELECT {cols} FROM {table}) TO STDOUT", buf)
            buf.seek(0)
            t.copy_expert(f"COPY {table} ({cols}) FROM STDIN", buf)
            t.execute(f"SELECT count(*) FROM {table}")
            print(f"{table:30} {t.fetchone()[0]}")
        # Supabase keeps its accounts in the auth schema; the local database has none.
        t.execute("SELECT to_regclass('auth.users') IS NOT NULL")
        if t.fetchone()[0]:
            t.execute(
                "UPDATE users u SET auth_id = a.id FROM auth.users a WHERE lower(a.email) = lower(u.email)"
            )
            print(f"Pointed {t.rowcount} user(s) at their staging sign-in account by email.")
    target.commit()
    prod.close()
    target.close()
    print("Copied production into", urlparse(target_url).hostname, urlparse(target_url).path.lstrip("/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
