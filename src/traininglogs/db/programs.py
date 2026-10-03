"""Programs, their workouts, and pinned exercise notes.

A program is workouts in order; after the last one it starts again at 1. Workouts keep their
order in `position`, always 1..n among the ones not archived. Each function that writes commits
its own transaction.
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from psycopg2.extensions import connection as Connection


def _new_id() -> str:
    return uuid.uuid4().hex


def _rows(cur) -> list[dict[str, Any]]:
    names = [d.name for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def list_programs(conn: Connection) -> list[dict[str, Any]]:
    """Every program not archived, the followed one first, each with its workouts."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, deload_after_days, following, following_since
            FROM programs WHERE archived_at IS NULL
            ORDER BY following DESC, created_at
            """
        )
        programs = _rows(cur)
    for p in programs:
        _attach_workouts(conn, p)
    return programs


def get_program(conn: Connection, program_id: str) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, deload_after_days, following, following_since
            FROM programs WHERE id = %s AND archived_at IS NULL
            """,
            (program_id,),
        )
        rows = _rows(cur)
    if not rows:
        return None
    return _attach_workouts(conn, rows[0])


def _attach_workouts(conn: Connection, program: dict[str, Any]) -> dict[str, Any]:
    """Adds `workouts` (in order, with exercises and the date each was last done) and
    `next_workout_id`."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT w.id, w.position, w.name,
                   (SELECT max(s.date) FROM sessions s WHERE s.program_workout_id = w.id) AS last_done
            FROM program_workouts w
            WHERE w.program_id = %s AND w.archived_at IS NULL
            ORDER BY w.position
            """,
            (program["id"],),
        )
        workouts = _rows(cur)
        cur.execute(
            """
            SELECT e.workout_id, e.name, e.warmup_sets, e.working_sets, e.target_reps, e.amrap
            FROM program_workout_exercises e
            JOIN program_workouts w ON w.id = e.workout_id
            WHERE w.program_id = %s
            ORDER BY e.position
            """,
            (program["id"],),
        )
        exercises = _rows(cur)
    for w in workouts:
        w["exercises"] = [
            {k: v for k, v in e.items() if k != "workout_id"} for e in exercises if e["workout_id"] == w["id"]
        ]
    program["workouts"] = workouts
    program["next_workout_id"] = _next_workout_id(conn, program["id"], workouts)
    return program


def _next_workout_id(conn: Connection, program_id: str, workouts: list[dict[str, Any]]) -> str | None:
    """The workout after the one in the program's most recent session; workout 1 when there is
    none, or after the last."""
    if not workouts:
        return None
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT w.position FROM sessions s
            JOIN program_workouts w ON w.id = s.program_workout_id
            WHERE w.program_id = %s AND w.archived_at IS NULL
            ORDER BY s.date DESC, s.created_at DESC
            LIMIT 1
            """,
            (program_id,),
        )
        row = cur.fetchone()
    if row is None:
        return workouts[0]["id"]
    later = [w for w in workouts if w["position"] > row[0]]
    return (later[0] if later else workouts[0])["id"]


def create_program(conn: Connection, name: str) -> str:
    program_id = _new_id()
    with conn.cursor() as cur:
        cur.execute("INSERT INTO programs (id, name) VALUES (%s, %s)", (program_id, name))
    conn.commit()
    return program_id


def update_program(
    conn: Connection, program_id: str, name: str | None = None, deload_after_days: int | None = None
) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE programs
            SET name = COALESCE(%s, name), deload_after_days = COALESCE(%s, deload_after_days)
            WHERE id = %s AND archived_at IS NULL
            """,
            (name, deload_after_days, program_id),
        )
        found = cur.rowcount == 1
    conn.commit()
    return found


def follow_program(conn: Connection, program_id: str, today: date) -> bool:
    """Follows this program and stops following any other. Following again keeps its start date."""
    with conn.cursor() as cur:
        cur.execute("SELECT following FROM programs WHERE id = %s AND archived_at IS NULL", (program_id,))
        row = cur.fetchone()
        if row is None:
            return False
        if not row[0]:
            cur.execute("UPDATE programs SET following = false WHERE following")
            cur.execute(
                "UPDATE programs SET following = true, following_since = %s WHERE id = %s",
                (today, program_id),
            )
    conn.commit()
    return True


def unfollow_program(conn: Connection, program_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE programs SET following = false WHERE id = %s AND archived_at IS NULL", (program_id,)
        )
        found = cur.rowcount == 1
    conn.commit()
    return found


def archive_program(conn: Connection, program_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE programs SET archived_at = now(), following = false
            WHERE id = %s AND archived_at IS NULL
            """,
            (program_id,),
        )
        found = cur.rowcount == 1
    conn.commit()
    return found


def add_workout(conn: Connection, program_id: str, name: str | None) -> str | None:
    """Adds a workout after the last one. None if the program doesn't exist."""
    workout_id = _new_id()
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM programs WHERE id = %s AND archived_at IS NULL", (program_id,))
        if cur.fetchone() is None:
            return None
        cur.execute(
            """
            INSERT INTO program_workouts (id, program_id, position, name)
            SELECT %s, %s, COALESCE(max(position), 0) + 1, %s
            FROM program_workouts WHERE program_id = %s AND archived_at IS NULL
            """,
            (workout_id, program_id, name, program_id),
        )
    conn.commit()
    return workout_id


def workout_program_id(conn: Connection, workout_id: str) -> str | None:
    """The program a workout belongs to, if the workout exists and isn't archived."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT program_id FROM program_workouts WHERE id = %s AND archived_at IS NULL", (workout_id,)
        )
        row = cur.fetchone()
    return row[0] if row else None


def rename_workout(conn: Connection, workout_id: str, name: str | None) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE program_workouts SET name = %s WHERE id = %s AND archived_at IS NULL",
            (name, workout_id),
        )
        found = cur.rowcount == 1
    conn.commit()
    return found


def reorder_workouts(conn: Connection, program_id: str, workout_ids: list[str]) -> bool:
    """Puts the program's workouts in this order. The list must name each of them exactly once."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM program_workouts WHERE program_id = %s AND archived_at IS NULL",
            (program_id,),
        )
        current = {r[0] for r in cur.fetchall()}
        if current != set(workout_ids) or len(workout_ids) != len(current):
            return False
        for position, workout_id in enumerate(workout_ids, start=1):
            cur.execute("UPDATE program_workouts SET position = %s WHERE id = %s", (position, workout_id))
    conn.commit()
    return True


def archive_workout(conn: Connection, workout_id: str) -> bool:
    """Archives a workout and closes the gap so the rest stay numbered 1..n."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE program_workouts SET archived_at = now()
            WHERE id = %s AND archived_at IS NULL
            RETURNING program_id, position
            """,
            (workout_id,),
        )
        row = cur.fetchone()
        if row is None:
            return False
        cur.execute(
            """
            UPDATE program_workouts SET position = position - 1
            WHERE program_id = %s AND archived_at IS NULL AND position > %s
            """,
            row,
        )
    conn.commit()
    return True


def set_workout_exercises(conn: Connection, workout_id: str, exercises: list[dict[str, Any]]) -> bool:
    """Replaces a workout's plan with these exercises, in this order."""
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM program_workouts WHERE id = %s AND archived_at IS NULL", (workout_id,))
        if cur.fetchone() is None:
            return False
        cur.execute("DELETE FROM program_workout_exercises WHERE workout_id = %s", (workout_id,))
        for position, e in enumerate(exercises, start=1):
            cur.execute(
                """
                INSERT INTO program_workout_exercises
                    (id, workout_id, position, name, warmup_sets, working_sets, target_reps, amrap)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    _new_id(), workout_id, position, e["name"], e["warmup_sets"],
                    e["working_sets"], e["target_reps"], e["amrap"],
                ),
            )
    conn.commit()
    return True


def name_key(name: str) -> str:
    """How exercise names are matched for pins: case and outer spaces ignored."""
    return name.strip().lower()


def list_pins(conn: Connection) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT name_key, note, pinned_at FROM exercise_pins ORDER BY name_key")
        return _rows(cur)


def set_pin(conn: Connection, exercise_name: str, note: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO exercise_pins (name_key, note) VALUES (%s, %s)
            ON CONFLICT (name_key) DO UPDATE SET note = EXCLUDED.note, pinned_at = now()
            """,
            (name_key(exercise_name), note),
        )
    conn.commit()


def remove_pin(conn: Connection, exercise_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM exercise_pins WHERE name_key = %s", (name_key(exercise_name),))
        found = cur.rowcount == 1
    conn.commit()
    return found
