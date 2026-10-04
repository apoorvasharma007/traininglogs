"""Adds Starting Strength Phase 4 (the advanced novice program) and links the sessions already logged.

Three workouts a week, each the same shape: squat, a press, a pull from the floor or back extensions,
and a chin-up or pull-up variant. The variation between weeks lives in each line's choices
("Shoulder Press or Bench press"): starting a workout picks the choice done longest ago, and the
session can still change anything. Every line is 5 x 5; warmup
sets are as many as in the latest logged session of the line's first exercise. Exercise names
are the ones used in the logs, so last time and Progress match.

The logged sessions (program `starting_strength_phase_4`) are linked to workouts 1, 2, 3 in turn,
in date order, and the program is followed, counting from the first of them.

Runs in one transaction; commits only if the counts come out as expected.

    .venv/bin/python scripts/add_starting_strength.py           # dev copy
    .venv/bin/python scripts/add_starting_strength.py --prod    # production: only with Apoorva's yes
"""
from __future__ import annotations

import os
import sys

import psycopg2
import psycopg2.extensions
from dotenv import load_dotenv

from traininglogs.db.programs import add_workout, create_program, follow_program, set_workout_exercises

DEFAULT_DEV_URL = "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_dev"
NAME = "Starting Strength · Phase 4"
SOURCE = "starting_strength_phase_4"

LINES = [
    ["Squat"],
    ["Shoulder Press", "Bench press"],
    ["Deadlift", "Barbell Clean", "Back extension"],
    ["Chinups", "Pull ups", "Weighted chin up", "Weighted pull up"],
]
WORKOUT_NAMES = [None, None, None]


class HeldCommits(psycopg2.extensions.connection):
    """The library functions commit as they go; here they are held so the run is one transaction."""

    hold = True

    def commit(self) -> None:
        if not self.hold:
            super().commit()


def _warmups(cur, name: str) -> int:
    cur.execute(
        """
        SELECT (SELECT count(*) FROM warmup_sets w WHERE w.exercise_id = e.id)
        FROM exercises e JOIN sessions s ON s.session_id = e.session_id
        WHERE lower(trim(e.name)) = lower(%s) ORDER BY s.date DESC, s.created_at DESC LIMIT 1
        """,
        (name,),
    )
    row = cur.fetchone()
    return row[0] if row else 0


def _counts(cur) -> dict[str, int]:
    out = {}
    for t in ("programs", "program_workouts", "program_workout_exercises", "sessions"):
        cur.execute(f"SELECT count(*) FROM {t}")
        out[t] = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM sessions WHERE program_workout_id IS NOT NULL")
    out["sessions linked"] = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM programs WHERE following")
    out["followed"] = cur.fetchone()[0]
    return out


def main() -> int:
    load_dotenv(".env")
    url = os.environ["DATABASE_URL"] if "--prod" in sys.argv else os.environ.get("DEV_DATABASE_URL", DEFAULT_DEV_URL)
    conn = psycopg2.connect(url, connection_factory=HeldCommits)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM programs WHERE name = %s AND archived_at IS NULL", (NAME,))
    if cur.fetchone():
        print(f"{NAME} already exists; nothing done.")
        return 1
    before = _counts(cur)

    plan = [
        {
            "name": choices[0], "alternatives": choices[1:], "warmup_sets": _warmups(cur, choices[0]),
            "working_sets": 5, "target_reps": 5, "amrap": False,
        }
        for choices in LINES
    ]
    program_id = create_program(conn, NAME)
    workout_ids = []
    for name in WORKOUT_NAMES:
        workout_id = add_workout(conn, program_id, name)
        set_workout_exercises(conn, workout_id, plan)
        workout_ids.append(workout_id)

    cur.execute("SELECT session_id, date FROM sessions WHERE program = %s ORDER BY date, created_at", (SOURCE,))
    logged = cur.fetchall()
    for i, (session_id, day) in enumerate(logged):
        cur.execute("UPDATE sessions SET program_workout_id = %s WHERE session_id = %s", (workout_ids[i % 3], session_id))
        print(f"  {day}  ->  workout {i % 3 + 1}")

    follow_program(conn, program_id, logged[0][1] if logged else None)

    after = _counts(cur)
    expected = dict(before)
    expected.update({
        "programs": before["programs"] + 1,
        "program_workouts": before["program_workouts"] + 3,
        "program_workout_exercises": before["program_workout_exercises"] + 3 * len(LINES),
        "sessions linked": before["sessions linked"] + len(logged),
        "followed": 1,
    })
    for k in after:
        if after[k] != before[k]:
            print(f"  {k}: {before[k]} -> {after[k]}")
    if after != expected:
        conn.rollback()
        print("ROLLED BACK: counts not as expected", expected)
        return 1
    HeldCommits.hold = False
    conn.commit()
    print(f"{NAME}: 3 workouts, {3 * len(LINES)} plan lines, {len(logged)} sessions linked, followed. COMMITTED")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
