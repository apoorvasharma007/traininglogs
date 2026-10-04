"""A program built from sessions already logged, and those sessions linked to it.

Past sessions carry the program as text (`sessions.program`), with phase, week and focus. This
turns one stretch of that history into a program in the app: one workout per focus, in the order
given, with the plan taken from one week of logged sessions -- each exercise in order, the warmup
sets as logged, the working sets the program asked for (`goal_sets`, else as logged), and the top
of the rep range as the target. Then every session of that focus within the weeks is linked to
its workout, so the program knows when each was last done and which comes next.
"""
from __future__ import annotations

from dataclasses import dataclass

from psycopg2.extensions import connection as Connection

from traininglogs.db.programs import add_workout, create_program, set_workout_exercises


@dataclass(frozen=True)
class HistoryProgram:
    name: str  # the program's name in the app
    source: str  # sessions.program of the sessions it comes from
    weeks: tuple[int, ...]  # the weeks of each phase that belong to it
    plan_phase: int  # where the plan is read from
    plan_week: int
    foci: tuple[str, ...]  # one workout per focus, in this order


def _plan(conn: Connection, p: HistoryProgram, focus: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.name, e.goal_sets, e.goal_rep_min, e.goal_rep_max,
                   (SELECT count(*) FROM warmup_sets w WHERE w.exercise_id = e.id),
                   (SELECT count(*) FROM working_sets w WHERE w.exercise_id = e.id)
            FROM sessions s JOIN exercises e ON e.session_id = s.session_id
            WHERE s.program = %s AND s.phase = %s AND s.week = %s AND s.focus = %s
              AND s.session_id = (
                  SELECT session_id FROM sessions
                  WHERE program = %s AND phase = %s AND week = %s AND focus = %s
                  ORDER BY date, created_at LIMIT 1)
            ORDER BY e.number
            """,
            (p.source, p.plan_phase, p.plan_week, focus) * 2,
        )
        rows = cur.fetchall()
    return [
        {
            "name": " ".join(name.split()),
            "warmup_sets": warmups,
            "working_sets": goal_sets or logged or 1,
            "target_reps": rep_max or rep_min,
            "amrap": False,
        }
        for name, goal_sets, rep_min, rep_max, warmups, logged in rows
    ]


def build_from_history(conn: Connection, p: HistoryProgram) -> dict:
    """Creates the program and links its past sessions. Refuses if a program by that name exists.
    Returns the program's id and, per workout, how many exercises and linked sessions it has."""
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM programs WHERE name = %s AND archived_at IS NULL", (p.name,))
        if cur.fetchone():
            raise ValueError(f"A program called {p.name!r} already exists")

    plans = {focus: _plan(conn, p, focus) for focus in p.foci}
    missing = [f for f, plan in plans.items() if not plan]
    if missing:
        raise ValueError(f"No sessions in phase {p.plan_phase}, week {p.plan_week} for: {', '.join(missing)}")

    program_id = create_program(conn, p.name)
    summary = {"program_id": program_id, "workouts": []}
    for focus in p.foci:
        workout_id = add_workout(conn, program_id, focus)
        set_workout_exercises(conn, workout_id, plans[focus])
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE sessions SET program_workout_id = %s
                WHERE program = %s AND focus = %s AND week = ANY(%s) AND program_workout_id IS NULL
                """,
                (workout_id, p.source, focus, list(p.weeks)),
            )
            linked = cur.rowcount
        conn.commit()
        summary["workouts"].append({"focus": focus, "exercises": len(plans[focus]), "sessions_linked": linked})
    return summary
