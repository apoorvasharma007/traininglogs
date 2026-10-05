"""Reading people's data. Every function takes the owner and only ever returns that person's rows.
The shapes match what the API has always sent, so the app doesn't change."""
from __future__ import annotations

from psycopg2.extensions import connection as Connection

from traininglogs.db.insert import name_key


def _rows(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def get_sessions(
    conn: Connection,
    user_id: str,
    phase: int | None = None,
    week: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    filters, params = ["s.user_id = %s"], [user_id]
    for clause, value in (("s.phase = %s", phase), ("s.week = %s", week),
                          ("s.date >= %s", from_date), ("s.date <= %s", to_date)):
        if value is not None:
            filters.append(clause)
            params.append(value)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT s.id::text AS session_id, s.date, s.program, s.phase, s.week, s.focus,
                   s.duration_minutes, s.is_deload_week, s.weight_unit,
                   ARRAY(SELECT e.name FROM workout_session_exercises e
                         WHERE e.user_id = s.user_id AND e.session_id = s.id ORDER BY e.position) AS exercises
            FROM workout_sessions s
            WHERE {" AND ".join(filters)}
            ORDER BY s.date DESC, s.created_at DESC
            {"LIMIT %s" if limit is not None else ""}
            """,
            params + ([limit] if limit is not None else []),
        )
        return _rows(cur)


_SET_COLUMNS = """position AS number, weight_kg, reps_full, reps_partial, left_reps_full,
    left_reps_partial, right_reps_full, right_reps_partial, rpe, rep_quality, rest_minutes,
    rest_seconds, duration_seconds, distance_meters, heart_rate_bpm, notes, failure_technique"""


def get_session(conn: Connection, user_id: str, session_id: str) -> dict | None:
    """A whole session: four queries, however many exercises and sets it has."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id::text AS session_id, date, program, program_author, program_length_weeks, phase,
                   week, is_deload_week, focus, duration_minutes, weight_unit, user_id::text AS user_id,
                   NULL AS user_name, source AS source_file, notes
            FROM workout_sessions WHERE user_id = %s AND id = %s
            """,
            (user_id, session_id),
        )
        found = _rows(cur)
        if not found:
            return None
        session = found[0]
        for key, table in (("warmup", "workout_session_warmups"), ("cooldown", "workout_session_cooldowns")):
            cur.execute(
                f"SELECT position AS number, name, reps, duration_seconds, notes FROM {table}"
                " WHERE user_id = %s AND session_id = %s ORDER BY position",
                (user_id, session_id),
            )
            session[key] = _rows(cur)
        cur.execute(
            """
            SELECT id, position AS number, name, tags, modality, movement_pattern, notes, warmup_notes,
                   form_cues, goal_weight_kg, goal_sets, goal_rep_min, goal_rep_max, goal_rest_min,
                   goal_rest_seconds, goal_distance_meters, goal_target_duration_sec,
                   target_muscle_groups, rep_tempo
            FROM workout_session_exercises WHERE user_id = %s AND session_id = %s ORDER BY position
            """,
            (user_id, session_id),
        )
        exercises = _rows(cur)
        cur.execute(
            f"""
            SELECT exercise_id, kind, {_SET_COLUMNS}
            FROM workout_session_sets
            WHERE user_id = %s AND exercise_id = ANY(%s::uuid[]) ORDER BY position
            """,
            (user_id, [str(e["id"]) for e in exercises]),
        )
        sets = _rows(cur)
    for exercise in exercises:
        mine = [s for s in sets if s["exercise_id"] == exercise["id"]]
        exercise["sets"] = [_set(s) for s in mine if s["kind"] == "working"]
        exercise["warmup_sets"] = [
            {"number": s["number"], "weight_kg": s["weight_kg"], "rep_count": s["reps_full"], "notes": s["notes"]}
            for s in mine if s["kind"] == "warmup"
        ]
        del exercise["id"]
    session["exercises"] = exercises
    return session


def _set(row: dict) -> dict:
    return {k: v for k, v in row.items() if k not in ("exercise_id", "kind")}


def get_exercise_history(conn: Connection, name: str, user_id: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.date, s.phase, s.week, s.id::text AS session_id, ws.position AS number, ws.weight_kg,
                   ws.reps_full, ws.reps_partial, ws.rpe, ws.rep_quality, ws.failure_technique
            FROM workout_session_sets ws
            JOIN workout_session_exercises e ON e.user_id = ws.user_id AND e.id = ws.exercise_id
            JOIN user_exercises ue ON ue.user_id = e.user_id AND ue.id = e.user_exercise_id
            JOIN workout_sessions s ON s.user_id = e.user_id AND s.id = e.session_id
            WHERE ws.user_id = %s AND ue.name_key = %s AND ws.kind = 'working'
            ORDER BY s.date, ws.position
            """,
            (user_id, name_key(name)),
        )
        return _rows(cur)


def get_input(conn: Connection, user_id: str, input_id: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id::text AS id, content, kind, client_id, source, created_at FROM input_text"
            " WHERE user_id = %s AND id = %s",
            (user_id, input_id),
        )
        found = _rows(cur)
    return found[0] if found else None


def get_input_by_client_id(conn: Connection, user_id: str, client_id: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id::text AS id, content, kind, client_id, source, created_at FROM input_text"
            " WHERE user_id = %s AND client_id = %s",
            (user_id, client_id),
        )
        found = _rows(cur)
    return found[0] if found else None


_CARD_COLUMNS = """id::text AS id, input_id::text AS input_id, model, prompt_version, extract,
    uncertain_fields, warnings, status, corrections, created_at, confirmed_at"""


def get_card(conn: Connection, user_id: str, card_id: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {_CARD_COLUMNS} FROM input_text_confirmation_cards WHERE user_id = %s AND id = %s",
            (user_id, card_id),
        )
        found = _rows(cur)
    return found[0] if found else None


def get_cards_for_input(conn: Connection, user_id: str, input_id: str) -> list[dict]:
    """Every reading of one note, newest first."""
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {_CARD_COLUMNS} FROM input_text_confirmation_cards"
            " WHERE user_id = %s AND input_id = %s ORDER BY created_at DESC",
            (user_id, input_id),
        )
        return _rows(cur)


def get_working_set_rows(conn: Connection, user_id: str) -> list[dict]:
    """Every working set with its session date, exercise name and goal weight: the input to the
    Progress view. Keys match analytics.strength.SetRow."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.id::text AS session_id, s.date, e.name AS exercise, ws.position AS number,
                   ws.weight_kg, ws.reps_full, ws.left_reps_full, ws.right_reps_full, ws.rpe,
                   e.goal_weight_kg
            FROM workout_session_sets ws
            JOIN workout_session_exercises e ON e.user_id = ws.user_id AND e.id = ws.exercise_id
            JOIN workout_sessions s ON s.user_id = e.user_id AND s.id = e.session_id
            WHERE ws.user_id = %s AND ws.kind = 'working'
            ORDER BY s.date, e.position, ws.position
            """,
            (user_id,),
        )
        return _rows(cur)


def get_last_exercises(conn: Connection, names: list[str], user_id: str) -> list[dict]:
    """For each name, the latest session that had that exercise (the person's exercise with that
    name, ignoring case and spaces): its date, the exercise note, and its warm-up and working sets.
    Names never logged are left out. Reps of a set done one side at a time are the weaker side."""
    keys = sorted({name_key(n) for n in names if n.strip()})
    if not keys:
        return []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (ue.name_key) e.id, e.name, e.notes, s.date, s.id::text AS session_id
            FROM workout_session_exercises e
            JOIN user_exercises ue ON ue.user_id = e.user_id AND ue.id = e.user_exercise_id
            JOIN workout_sessions s ON s.user_id = e.user_id AND s.id = e.session_id
            WHERE e.user_id = %s AND ue.name_key = ANY(%s)
            ORDER BY ue.name_key, s.date DESC, s.created_at DESC, e.position
            """,
            (user_id, keys),
        )
        found = _rows(cur)
        cur.execute(
            """
            SELECT exercise_id, kind, weight_kg, COALESCE(reps_full, LEAST(left_reps_full, right_reps_full)) AS reps,
                   rpe, notes
            FROM workout_session_sets WHERE user_id = %s AND exercise_id = ANY(%s::uuid[]) ORDER BY position
            """,
            (user_id, [str(f["id"]) for f in found]),
        )
        sets = _rows(cur)
    result = []
    for f in found:
        mine = [s for s in sets if s["exercise_id"] == f["id"]]
        result.append({
            "name": f["name"], "date": f["date"], "session_id": f["session_id"], "notes": f["notes"],
            "warmup_sets": [{"weight_kg": s["weight_kg"], "reps": s["reps"], "notes": s["notes"]}
                            for s in mine if s["kind"] == "warmup"],
            "sets": [{"weight_kg": s["weight_kg"], "reps": s["reps"], "rpe": s["rpe"], "notes": s["notes"]}
                     for s in mine if s["kind"] == "working"],
        })
    return result
