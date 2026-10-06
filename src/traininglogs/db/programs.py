"""Programs and their workouts, always one person's.

A program is workouts in order; after the last one it starts again at 1. Workouts keep their order
in `position`, always 1..n among the ones not archived. Every function takes the owner and only
touches that person's rows: someone else's program behaves exactly like one that doesn't exist.
Each function that writes commits its own transaction.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from psycopg2.extensions import connection as Connection

from traininglogs.db.fetch import _rows
from traininglogs.db.ids import new_id
from traininglogs.db.insert import name_key, user_exercise_ids


def utc_today() -> date:
    """Today in UTC, for counts of days (deload, trends), where a day early or late around midnight
    doesn't matter. Dates that are the person's data, like a session's, come from their phone."""
    return datetime.now(timezone.utc).date()


_PROGRAM = "SELECT id::text AS id, name, deload_after_days, following, following_since FROM programs"


def list_programs(conn: Connection, user_id: str) -> list[dict[str, Any]]:
    """The person's programs not archived, the followed one first, each with its workouts."""
    with conn.cursor() as cur:
        cur.execute(f"{_PROGRAM} WHERE user_id = %s AND archived_at IS NULL ORDER BY following DESC, created_at", (user_id,))
        programs = _rows(cur)
    return [_attach_workouts(conn, user_id, p, utc_today()) for p in programs]


def get_program(conn: Connection, user_id: str, program_id: str) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(f"{_PROGRAM} WHERE user_id = %s AND id = %s AND archived_at IS NULL", (user_id, program_id))
        rows = _rows(cur)
    return _attach_workouts(conn, user_id, rows[0], utc_today()) if rows else None


def _attach_workouts(conn: Connection, user_id: str, program: dict[str, Any], today: date) -> dict[str, Any]:
    """Adds `workouts` (in order, with exercises and the date each was last done),
    `next_workout_id` and `deload`."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT w.id::text AS id, w.position, w.name, w.warmup, w.cooldown,
                   (SELECT max(s.date) FROM workout_sessions s
                    WHERE s.user_id = w.user_id AND s.program_workout_id = w.id) AS last_done
            FROM program_workouts w
            WHERE w.user_id = %s AND w.program_id = %s AND w.archived_at IS NULL
            ORDER BY w.position
            """,
            (user_id, program["id"]),
        )
        workouts = _rows(cur)
        cur.execute(
            """
            SELECT e.workout_id::text AS workout_id, e.name, e.warmup_sets, e.working_sets, e.target_reps,
                   e.amrap, e.alternatives
            FROM program_workout_exercises e
            JOIN program_workouts w ON w.user_id = e.user_id AND w.id = e.workout_id
            WHERE e.user_id = %s AND w.program_id = %s
            ORDER BY e.position
            """,
            (user_id, program["id"]),
        )
        exercises = _rows(cur)
    for w in workouts:
        w["exercises"] = [{k: v for k, v in e.items() if k != "workout_id"} for e in exercises if e["workout_id"] == w["id"]]
    program["workouts"] = workouts
    program["next_workout_id"] = _next_workout_id(conn, user_id, program["id"], workouts)
    program["deload"] = deload_status(conn, user_id, program, today)
    return program


# A break this long with no training restarts the deload count.
BREAK_DAYS = 7


def deload_status(conn: Connection, user_id: str, program: dict[str, Any], today: date) -> dict[str, Any]:
    """How long the program has gone without a deload, and whether one is under way.

    The count runs from the latest of: the day the program was followed, the day after its last
    deload session, and the first session after a break of BREAK_DAYS or more with no training
    at all. A break that is still going on (no session in the last BREAK_DAYS days) makes it 0.
    `in_progress` is how many of the program's latest sessions in a row were deload sessions.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.date, COALESCE(s.is_deload_week, false)
            FROM workout_sessions s JOIN program_workouts w ON w.user_id = s.user_id AND w.id = s.program_workout_id
            WHERE s.user_id = %s AND w.program_id = %s ORDER BY s.date, s.created_at
            """,
            (user_id, program["id"]),
        )
        own = cur.fetchall()
        cur.execute(
            "SELECT DISTINCT date FROM workout_sessions WHERE user_id = %s AND date <= %s ORDER BY date",
            (user_id, today),
        )
        trained = [r[0] for r in cur.fetchall()]

    in_progress = 0
    for _, deload in reversed(own):
        if not deload:
            break
        in_progress += 1

    starts = []
    if program.get("following") and program.get("following_since"):
        starts.append(program["following_since"])
    deloads = [d for d, deload in own if deload]
    if deloads:
        starts.append(deloads[-1] + timedelta(days=1))
    after_break = [b for a, b in zip(trained, trained[1:]) if (b - a).days >= BREAK_DAYS]
    if after_break:
        starts.append(after_break[-1])
    if not starts and own:
        starts.append(own[0][0])

    on_break = not trained or (today - trained[-1]).days >= BREAK_DAYS
    days = 0 if on_break or not starts else max(0, (today - max(starts)).days)
    return {
        "days_since": days,
        "due": days >= program["deload_after_days"] and in_progress == 0,
        "in_progress": in_progress,
    }


def _next_workout_id(conn: Connection, user_id: str, program_id: str, workouts: list[dict[str, Any]]) -> str | None:
    """The workout after the one in the program's most recent session; workout 1 when there is
    none, or after the last."""
    if not workouts:
        return None
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT w.position FROM workout_sessions s
            JOIN program_workouts w ON w.user_id = s.user_id AND w.id = s.program_workout_id
            WHERE s.user_id = %s AND w.program_id = %s AND w.archived_at IS NULL
            ORDER BY s.date DESC, s.created_at DESC
            LIMIT 1
            """,
            (user_id, program_id),
        )
        row = cur.fetchone()
    if row is None:
        return workouts[0]["id"]
    later = [w for w in workouts if w["position"] > row[0]]
    return (later[0] if later else workouts[0])["id"]


def _insert_exercises(cur, user_id: str, workout_id: str, exercises: list[dict[str, Any]]) -> None:
    ids = user_exercise_ids(cur, user_id, [e["name"] for e in exercises])
    for position, e in enumerate(exercises, start=1):
        cur.execute(
            """
            INSERT INTO program_workout_exercises (id, user_id, workout_id, position, user_exercise_id, name,
                warmup_sets, working_sets, target_reps, amrap, alternatives)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                new_id(), user_id, workout_id, position, ids[name_key(e["name"])], e["name"], e["warmup_sets"],
                e["working_sets"], e["target_reps"], e["amrap"], list(e.get("alternatives") or []),
            ),
        )


def create_program(conn: Connection, user_id: str, name: str, workouts: list[dict[str, Any]] = ()) -> str:
    """Creates a program, with any workouts and their exercises, in one transaction, so a failure
    leaves nothing behind. Each workout is {"name", "exercises"}, exercises as in
    set_workout_exercises."""
    program_id = new_id()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO programs (id, user_id, name) VALUES (%s, %s, %s)", (program_id, user_id, name))
            for position, w in enumerate(workouts, start=1):
                workout_id = new_id()
                cur.execute(
                    "INSERT INTO program_workouts (id, user_id, program_id, position, name) VALUES (%s, %s, %s, %s, %s)",
                    (workout_id, user_id, program_id, position, w["name"]),
                )
                _insert_exercises(cur, user_id, workout_id, w["exercises"])
    except Exception:
        conn.rollback()
        raise
    conn.commit()
    return program_id


def _update(conn: Connection, sql: str, params: tuple) -> bool:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        found = cur.rowcount == 1
    conn.commit()
    return found


def update_program(
    conn: Connection, user_id: str, program_id: str, name: str | None = None, deload_after_days: int | None = None
) -> bool:
    return _update(
        conn,
        """
        UPDATE programs SET name = COALESCE(%s, name), deload_after_days = COALESCE(%s, deload_after_days),
               updated_at = now()
        WHERE user_id = %s AND id = %s AND archived_at IS NULL
        """,
        (name, deload_after_days, user_id, program_id),
    )


def follow_program(conn: Connection, user_id: str, program_id: str) -> bool:
    """Follows this program and stops following the person's other one. Following again keeps its
    start date."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT following FROM programs WHERE user_id = %s AND id = %s AND archived_at IS NULL", (user_id, program_id)
        )
        row = cur.fetchone()
        if row is None:
            return False
        if not row[0]:
            cur.execute("UPDATE programs SET following = false, updated_at = now() WHERE user_id = %s AND following", (user_id,))
            cur.execute(
                "UPDATE programs SET following = true, following_since = %s, updated_at = now() WHERE user_id = %s AND id = %s",
                (utc_today(), user_id, program_id),
            )
    conn.commit()
    return True


def unfollow_program(conn: Connection, user_id: str, program_id: str) -> bool:
    return _update(
        conn,
        "UPDATE programs SET following = false, updated_at = now() WHERE user_id = %s AND id = %s AND archived_at IS NULL",
        (user_id, program_id),
    )


def archive_program(conn: Connection, user_id: str, program_id: str) -> bool:
    return _update(
        conn,
        "UPDATE programs SET archived_at = now(), following = false, updated_at = now()"
        " WHERE user_id = %s AND id = %s AND archived_at IS NULL",
        (user_id, program_id),
    )


def add_workout(conn: Connection, user_id: str, program_id: str, name: str | None) -> str | None:
    """Adds a workout after the last one. None if the person has no such program."""
    workout_id = new_id()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO program_workouts (id, user_id, program_id, position, name)
            SELECT %s, %s, %s,
                   (SELECT COALESCE(max(position), 0) + 1 FROM program_workouts
                    WHERE user_id = %s AND program_id = %s AND archived_at IS NULL),
                   %s
            WHERE EXISTS (SELECT 1 FROM programs WHERE user_id = %s AND id = %s AND archived_at IS NULL)
            """,
            (workout_id, user_id, program_id, user_id, program_id, name, user_id, program_id),
        )
        added = cur.rowcount == 1
    conn.commit()
    return workout_id if added else None


def workout_program_id(conn: Connection, user_id: str, workout_id: str) -> str | None:
    """The program a workout belongs to, if the person has that workout and it isn't archived."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT program_id::text FROM program_workouts WHERE user_id = %s AND id = %s AND archived_at IS NULL",
            (user_id, workout_id),
        )
        row = cur.fetchone()
    return row[0] if row else None


def set_workout_movements(conn: Connection, user_id: str, workout_id: str, warmup: list[dict], cooldown: list[dict]) -> bool:
    """Replaces a workout's warm-up and cool-down movements."""
    return _update(
        conn,
        "UPDATE program_workouts SET warmup = %s::jsonb, cooldown = %s::jsonb, updated_at = now()"
        " WHERE user_id = %s AND id = %s AND archived_at IS NULL",
        (json.dumps(warmup), json.dumps(cooldown), user_id, workout_id),
    )


def rename_workout(conn: Connection, user_id: str, workout_id: str, name: str | None) -> bool:
    return _update(
        conn,
        "UPDATE program_workouts SET name = %s, updated_at = now() WHERE user_id = %s AND id = %s AND archived_at IS NULL",
        (name, user_id, workout_id),
    )


def reorder_workouts(conn: Connection, user_id: str, program_id: str, workout_ids: list[str]) -> bool:
    """Puts the program's workouts in this order. The list must name each of them exactly once."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id::text FROM program_workouts WHERE user_id = %s AND program_id = %s AND archived_at IS NULL",
            (user_id, program_id),
        )
        current = {r[0] for r in cur.fetchall()}
        if current != set(workout_ids) or len(workout_ids) != len(current):
            return False
        for position, workout_id in enumerate(workout_ids, start=1):
            cur.execute(
                "UPDATE program_workouts SET position = %s, updated_at = now() WHERE user_id = %s AND id = %s",
                (position, user_id, workout_id),
            )
    conn.commit()
    return True


def archive_workout(conn: Connection, user_id: str, workout_id: str) -> bool:
    """Archives a workout and closes the gap so the rest stay numbered 1..n."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE program_workouts SET archived_at = now(), updated_at = now()
            WHERE user_id = %s AND id = %s AND archived_at IS NULL
            RETURNING program_id, position
            """,
            (user_id, workout_id),
        )
        row = cur.fetchone()
        if row is None:
            return False
        cur.execute(
            """
            UPDATE program_workouts SET position = position - 1, updated_at = now()
            WHERE user_id = %s AND program_id = %s AND archived_at IS NULL AND position > %s
            """,
            (user_id, *row),
        )
    conn.commit()
    return True


def set_workout_exercises(conn: Connection, user_id: str, workout_id: str, exercises: list[dict[str, Any]]) -> bool:
    """Replaces a workout's plan with these exercises, in this order."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM program_workouts WHERE user_id = %s AND id = %s AND archived_at IS NULL", (user_id, workout_id)
        )
        if cur.fetchone() is None:
            return False
        cur.execute("DELETE FROM program_workout_exercises WHERE user_id = %s AND workout_id = %s", (user_id, workout_id))
        _insert_exercises(cur, user_id, workout_id, exercises)
    conn.commit()
    return True
