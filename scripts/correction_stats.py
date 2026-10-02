"""Which fields get corrected most, from confirmed extractions' corrections log. Read-only.

    .venv/bin/python scripts/correction_stats.py            # DATABASE_URL
    .venv/bin/python scripts/correction_stats.py --db-url postgresql://...
"""
from __future__ import annotations

import argparse
import os

import psycopg2
from dotenv import load_dotenv

from traininglogs.analytics.corrections import summarize


def load(db_url: str) -> dict[str, list[dict]]:
    conn = psycopg2.connect(db_url, connect_timeout=10)
    conn.set_session(readonly=True)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, corrections FROM extractions WHERE status = 'confirmed'")
            return dict(cur.fetchall())
    finally:
        conn.close()


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db-url", default=os.environ.get("DATABASE_URL"))
    args = parser.parse_args()
    if not args.db_url:
        raise SystemExit("DATABASE_URL not set and --db-url not given")

    summary = summarize(load(args.db_url))
    print(
        f"{summary.sessions_with_corrections} of {summary.sessions_total} confirmed sessions "
        "had corrections.\n"
    )

    print(f"{'field':<42} {'manual':>6} {'ai':>4} {'total':>5} {'sessions':>8}")
    for f in summary.fields:
        print(
            f"{f.pattern:<42} {f.by_source['manual']:>6} {f.by_source['ai']:>4} "
            f"{f.total:>5} {len(f.sessions):>8}"
        )

    if summary.ops:
        print("\nadded / removed lines")
        for op, count in summary.ops.most_common():
            print(f"  {op:<16} {count}")


if __name__ == "__main__":
    main()
