"""Copy production into the local dev database or staging, so the app can be tried on real data.

Reads production (DATABASE_URL) in a read-only transaction and never writes to it. Applies
schema.sql to the target, empties its tables and copies every table in. The target is
DEV_DATABASE_URL: the `traininglogs_dev` database in the local Docker Postgres by default, or
staging's database (DATABASE_URL_STAGING); anything else is refused. Run it again any time to
start fresh.

    .venv/bin/python scripts/copy_prod_to_dev.py
    DEV_DATABASE_URL="$DATABASE_URL_STAGING" .venv/bin/python scripts/copy_prod_to_dev.py

Then run the app against the copy:

    DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_dev \\
        .venv/bin/uvicorn traininglogs.api.app:app --port 8010
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

# Parents before children, so foreign keys hold while copying.
TABLES = [
    "raw_inputs", "extractions", "llm_calls",
    "programs", "program_workouts", "program_workout_exercises",
    "sessions", "warmups", "cooldowns", "exercises", "working_sets", "warmup_sets",
]


def _columns(cur, table: str) -> list[str]:
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' "
        "AND table_name = %s ORDER BY ordinal_position",
        (table,),
    )
    return [r[0] for r in cur.fetchall()]


def main() -> int:
    load_dotenv(".env")
    prod_url = os.environ["DATABASE_URL"]
    dev_url = os.environ.get("DEV_DATABASE_URL", DEFAULT_DEV_URL)
    allowed = urlparse(dev_url).hostname in ("localhost", "127.0.0.1") or dev_url == os.environ.get("DATABASE_URL_STAGING")
    if not allowed or dev_url == prod_url:
        print(f"Refusing: the target must be on this machine or be staging, got {urlparse(dev_url).hostname}")
        return 1

    prod = psycopg2.connect(prod_url)
    prod.set_session(readonly=True)
    dev = psycopg2.connect(dev_url)

    # Emptied rather than dropped: on Supabase the public schema also carries Supabase's own grants.
    apply_schema(dev)
    with dev.cursor() as cur:
        cur.execute(f"TRUNCATE {', '.join(TABLES)} CASCADE")

    with prod.cursor() as p, dev.cursor() as d:
        for table in TABLES:
            # Only the columns both have: prod may lack a column schema.sql added later.
            shared = [c for c in _columns(p, table) if c in set(_columns(d, table))]
            cols = ", ".join(f'"{c}"' for c in shared)
            buf = io.StringIO()
            p.copy_expert(f"COPY (SELECT {cols} FROM {table}) TO STDOUT", buf)
            buf.seek(0)
            d.copy_expert(f"COPY {table} ({cols}) FROM STDIN", buf)
            d.execute(f"SELECT count(*) FROM {table}")
            print(f"{table:28} {d.fetchone()[0]}")
            # Serial ids continue after the copied rows.
            seq = None
            if "id" in shared:
                d.execute("SELECT pg_get_serial_sequence(%s, 'id')", (table,))
                seq = d.fetchone()[0]
            if seq:
                d.execute(f"SELECT setval(%s, COALESCE((SELECT max(id) FROM {table}), 0) + 1, false)", (seq,))
    dev.commit()
    prod.close()
    dev.close()
    print("Copied production into", urlparse(dev_url).hostname, urlparse(dev_url).path.lstrip("/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
