"""Adds Bodybuilding Transformation as two programs, from the sessions already logged.

Each 12-week phase of the program is two halves with different exercises: Foundation (weeks 1-6)
and Ramp-up (weeks 7-12). The plans come from the first week of each half in phase 3, the latest;
sessions from both phases are linked to the matching workout.

Runs against the local dev database unless told otherwise. The programs belong to the user
whose users.id is in OWNER_USER_ID, and only that user's sessions are linked:

    .venv/bin/python scripts/add_bts_programs.py            # dev copy
    .venv/bin/python scripts/add_bts_programs.py --prod     # production: only with Apoorva's yes
"""
from __future__ import annotations

import os
import sys

import psycopg2
from dotenv import load_dotenv

from traininglogs.ingest.program_history import HistoryProgram, build_from_history

DEFAULT_DEV_URL = "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_dev"
SOURCE = "bodybuilding_transformation_system"
FOCI = ("Upper Strength", "Lower Strength", "Pull Hypertrophy", "Push Hypertrophy", "Legs Hypertrophy")

PROGRAMS = (
    HistoryProgram("Bodybuilding Transformation · Foundation", SOURCE, tuple(range(1, 7)), 3, 1, FOCI),
    HistoryProgram("Bodybuilding Transformation · Ramp-up", SOURCE, tuple(range(7, 13)), 3, 7, FOCI),
)


def main() -> int:
    load_dotenv(".env")
    url = os.environ["DATABASE_URL"] if "--prod" in sys.argv else os.environ.get("DEV_DATABASE_URL", DEFAULT_DEV_URL)
    conn = psycopg2.connect(url)
    for p in PROGRAMS:
        summary = build_from_history(conn, p, os.environ["OWNER_USER_ID"])
        print(p.name)
        for w in summary["workouts"]:
            print(f"  {w['focus']:18} {w['exercises']:2} exercises, {w['sessions_linked']:2} past sessions linked")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
