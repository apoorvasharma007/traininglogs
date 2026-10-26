"""Reading people's data. Every function takes the owner and only ever returns that person's rows.
The shapes match what the API has always sent, so the app doesn't change."""
from __future__ import annotations

from datetime import date

from psycopg2.extensions import connection as Connection

from traininglogs.analytics.key_lifts import DEFAULT_KEY_LIFTS
from traininglogs.db.insert import MY_EXERCISE_COLUMNS


# Which exercise a session exercise `e` counts as: `l`, its library exercise or the one its custom
# exercise links to; otherwise `c`, the custom exercise itself. Used with _COUNTS_AS_JOINS.
_COUNTS_AS = """l.id::text AS library_exercise_id, CASE WHEN l.id IS NULL THEN c.id::text END AS custom_exercise_id,
    coalesce(l.name, c.name) AS exercise"""
_COUNTS_AS_JOINS = """
    LEFT JOIN custom_exercises c ON c.user_id = e.user_id AND c.id = e.custom_exercise_id
    LEFT JOIN library_exercises l ON l.id = coalesce(e.library_exercise_id, c.linked_library_exercise_id)
"""


def _rows(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def get_sessions(
    conn: Connection,
    user_id: str,
    phase: int | None = None,
    week: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
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
                         WHERE e.user_id = s.user_id AND e.session_id = s.id ORDER BY e.position) AS exercises,
                   p.name AS program_name, w.position AS workout_position, w.name AS workout_name,
                   i.kind AS source_kind
            FROM workout_sessions s
            JOIN input_text i ON i.user_id = s.user_id AND i.id = s.input_id
            LEFT JOIN program_workouts w ON w.user_id = s.user_id AND w.id = s.program_workout_id
            LEFT JOIN programs p ON p.user_id = w.user_id AND p.id = w.program_id
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
            SELECT s.id::text AS session_id, s.date, s.program, s.program_author, s.program_length_weeks, s.phase,
                   s.week, s.is_deload_week, s.focus, s.duration_minutes, s.weight_unit, s.user_id::text AS user_id,
                   NULL AS user_name, s.source AS source_file, s.notes,
                   p.name AS program_name, w.position AS workout_position, w.name AS workout_name,
                   i.kind AS source_kind
            FROM workout_sessions s
            JOIN input_text i ON i.user_id = s.user_id AND i.id = s.input_id
            LEFT JOIN program_workouts w ON w.user_id = s.user_id AND w.id = s.program_workout_id
            LEFT JOIN programs p ON p.user_id = w.user_id AND p.id = w.program_id
            WHERE s.user_id = %s AND s.id = %s
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
            SELECT id, position AS number, library_exercise_id::text AS library_exercise_id,
                   custom_exercise_id::text AS custom_exercise_id, name, notes, warmup_notes, form_cues,
                   goal_weight_kg, goal_sets,
                   goal_rep_min, goal_rep_max, goal_rest_min, goal_rest_seconds, goal_distance_meters,
                   goal_target_duration_sec
            FROM workout_session_exercises WHERE user_id = %s AND session_id = %s ORDER BY position
            """,
            (user_id, session_id),
        )
        exercises = _rows(cur)
        cur.execute(
            f"""
            SELECT session_exercise_id, kind, {_SET_COLUMNS}
            FROM workout_session_sets
            WHERE user_id = %s AND session_exercise_id = ANY(%s::uuid[]) ORDER BY position
            """,
            (user_id, [str(e["id"]) for e in exercises]),
        )
        sets = _rows(cur)
    for exercise in exercises:
        mine = [s for s in sets if s["session_exercise_id"] == exercise["id"]]
        exercise["sets"] = [_set(s) for s in mine if s["kind"] == "working"]
        exercise["warmup_sets"] = [
            {"number": s["number"], "weight_kg": s["weight_kg"], "rep_count": s["reps_full"], "notes": s["notes"]}
            for s in mine if s["kind"] == "warmup"
        ]
        del exercise["id"]
    session["exercises"] = exercises
    return session


def _set(row: dict) -> dict:
    return {k: v for k, v in row.items() if k not in ("session_exercise_id", "kind")}


def get_ai_total_usd(conn: Connection, user_id: str) -> float:
    """What the person's AI calls have cost so far, in US dollars, summed from their call log.
    A few rows per note, so summing on each request is cheaper than keeping a running total."""
    with conn.cursor() as cur:
        cur.execute("SELECT coalesce(sum(cost_usd), 0) FROM ai_call_logs WHERE user_id = %s", (user_id,))
        return float(cur.fetchone()[0])


def get_key_lifts(conn: Connection, user_id: str) -> list[dict]:
    """The lifts Progress shows first, in order: the person's pins, or DEFAULT_KEY_LIFTS when they
    have none. Each is {library_exercise_id, custom_exercise_id, name, bodyweight}; a pin whose
    exercise is gone is left out."""
    with conn.cursor() as cur:
        cur.execute("SELECT key_lifts FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        pins = row[0] if row else None
        cur.execute(
            """
            SELECT library_exercise_id, custom_exercise_id, name, bodyweight FROM (
                SELECT k.n, l.id::text AS library_exercise_id, NULL AS custom_exercise_id, l.name,
                       l.equipment = 'bodyweight' AS bodyweight
                FROM unnest(%(wanted)s::text[]) WITH ORDINALITY k (v, n)
                JOIN library_exercises l ON (CASE WHEN %(by_name)s THEN l.name ELSE l.id::text END) = k.v
                UNION ALL
                SELECT k.n, NULL, c.id::text, c.name, coalesce(c.equipment = 'bodyweight', false)
                FROM unnest(%(wanted)s::text[]) WITH ORDINALITY k (v, n)
                JOIN custom_exercises c ON c.user_id = %(user_id)s AND c.id::text = k.v
            ) found ORDER BY n
            """,
            {"wanted": list(DEFAULT_KEY_LIFTS) if pins is None else pins, "by_name": pins is None, "user_id": user_id},
        )
        return _rows(cur)


def get_email(conn: Connection, user_id: str) -> str | None:
    """The person's email, as their sign-in account has it."""
    with conn.cursor() as cur:
        cur.execute("SELECT email FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
    return row[0] if row else None


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
    """Every working set with its session date, the exercise it counts as, and goal weight: the
    input to the Progress view. Keys match analytics.strength.SetRow."""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT s.id::text AS session_id, s.date, {_COUNTS_AS}, ws.position AS number,
                   ws.weight_kg, ws.reps_full, ws.left_reps_full, ws.right_reps_full, ws.rpe,
                   e.goal_weight_kg, coalesce(coalesce(l.equipment, c.equipment) = 'bodyweight', false) AS bodyweight
            FROM workout_session_sets ws
            JOIN workout_session_exercises e ON e.user_id = ws.user_id AND e.id = ws.session_exercise_id
            JOIN workout_sessions s ON s.user_id = e.user_id AND s.id = e.session_id
            {_COUNTS_AS_JOINS}
            WHERE ws.user_id = %s AND ws.kind = 'working'
            ORDER BY s.date, e.position, ws.position
            """,
            (user_id,),
        )
        return _rows(cur)


def get_exercises(conn: Connection, user_id: str) -> dict[str, list[dict]]:
    """The shared library and the person's custom exercises, sorted by name, for the phone to keep."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id::text, name, other_names, equipment, measures, compound, primary_muscles,
                   secondary_muscles, joint_actions, movement_patterns
            FROM library_exercises ORDER BY name
            """
        )
        library = _rows(cur)
        cur.execute(f"SELECT {MY_EXERCISE_COLUMNS} FROM custom_exercises WHERE user_id = %s ORDER BY name", (user_id,))
        mine = _rows(cur)
    return {"library": library, "mine": mine}


def get_last_exercises(conn: Connection, user_id: str, refs: list[dict]) -> list[dict]:
    """For each exercise (a ref: library_exercise_id or custom_exercise_id), the latest session that
    had it or anything counting as the same exercise: its date, the exercise note, and its warm-up
    and working sets, under the ref asked for. Exercises never logged are left out. Reps of a set
    done one side at a time are the weaker side."""
    if not refs:
        return []
    with conn.cursor() as cur:
        cur.execute(
            f"""
            WITH asked AS (
                SELECT a.n, a.library_exercise_id, a.custom_exercise_id,
                       coalesce(a.library_exercise_id, c.linked_library_exercise_id::text, a.custom_exercise_id) AS counts_as
                FROM unnest(%s::text[], %s::text[]) WITH ORDINALITY a (library_exercise_id, custom_exercise_id, n)
                LEFT JOIN custom_exercises c ON c.user_id = %s AND c.id::text = a.custom_exercise_id
            )
            SELECT DISTINCT ON (asked.n) asked.library_exercise_id, asked.custom_exercise_id, e.id, e.name,
                   e.notes, s.date, s.id::text AS session_id
            FROM workout_session_exercises e
            JOIN workout_sessions s ON s.user_id = e.user_id AND s.id = e.session_id
            {_COUNTS_AS_JOINS}
            JOIN asked ON asked.counts_as = coalesce(l.id, c.id)::text
            WHERE e.user_id = %s
            ORDER BY asked.n, s.date DESC, s.created_at DESC, e.position
            """,
            (
                [r.get("library_exercise_id") for r in refs], [r.get("custom_exercise_id") for r in refs],
                user_id, user_id,
            ),
        )
        found = _rows(cur)
        cur.execute(
            """
            SELECT session_exercise_id, kind, weight_kg,
                   COALESCE(reps_full, LEAST(left_reps_full, right_reps_full)) AS reps, rpe, notes
            FROM workout_session_sets WHERE user_id = %s AND session_exercise_id = ANY(%s::uuid[]) ORDER BY position
            """,
            (user_id, [str(f["id"]) for f in found]),
        )
        sets = _rows(cur)
    result = []
    for f in found:
        mine = [s for s in sets if s["session_exercise_id"] == f["id"]]
        result.append({
            "library_exercise_id": f["library_exercise_id"], "custom_exercise_id": f["custom_exercise_id"],
            "name": f["name"], "date": f["date"], "session_id": f["session_id"], "notes": f["notes"],
            "warmup_sets": [{"weight_kg": s["weight_kg"], "reps": s["reps"], "notes": s["notes"]}
                            for s in mine if s["kind"] == "warmup"],
            "sets": [{"weight_kg": s["weight_kg"], "reps": s["reps"], "rpe": s["rpe"], "notes": s["notes"]}
                     for s in mine if s["kind"] == "working"],
        })
    return result


def get_export_rows(conn: Connection, user_id: str) -> list[dict]:
    """Every set the person has logged, one row each, with its exercise and session, oldest first:
    what Export builds its CSV and JSON from. A session with no sets still gives one row (set
    columns empty), so nothing logged is left out."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.id::text AS session_id, s.date, s.focus, s.notes AS session_notes,
                   s.duration_minutes, s.program, p.name AS program_name, w.position AS workout_position,
                   w.name AS workout_name, e.position AS exercise_number, e.name AS exercise,
                   e.notes AS exercise_notes, x.kind AS set_kind, x.position AS set_number,
                   x.weight_kg, x.reps_full AS reps, x.reps_partial, x.rpe, x.duration_seconds,
                   x.distance_meters, x.notes AS set_notes
            FROM workout_sessions s
            LEFT JOIN program_workouts w ON w.user_id = s.user_id AND w.id = s.program_workout_id
            LEFT JOIN programs p ON p.user_id = w.user_id AND p.id = w.program_id
            LEFT JOIN workout_session_exercises e ON e.user_id = s.user_id AND e.session_id = s.id
            LEFT JOIN workout_session_sets x ON x.user_id = e.user_id AND x.session_exercise_id = e.id
            WHERE s.user_id = %s
            ORDER BY s.date, s.created_at, e.position, x.kind, x.position  -- warmup sorts before working
            """,
            (user_id,),
        )
        return _rows(cur)
