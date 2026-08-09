from psycopg2.extensions import connection as Connection


def get_sessions(
    conn: Connection,
    phase: int | None = None,
    week: int | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[dict]:
    filters = []
    params = []

    if phase is not None:
        filters.append("phase = %s")
        params.append(phase)
    if week is not None:
        filters.append("week = %s")
        params.append(week)
    if from_date is not None:
        filters.append("date >= %s")
        params.append(from_date)
    if to_date is not None:
        filters.append("date <= %s")
        params.append(to_date)

    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT session_id, date, program, phase, week, focus, duration_minutes,
                   is_deload_week, weight_unit
            FROM sessions
            {where}
            ORDER BY date DESC
            """,
            params,
        )
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

    return [dict(zip(cols, row)) for row in rows]


def get_session(conn: Connection, session_id: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT session_id, date, program, program_author, program_length_weeks,
                   phase, week, is_deload_week, focus, duration_minutes, weight_unit,
                   user_id, user_name, source_file, notes
            FROM sessions WHERE session_id = %s
            """,
            (session_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        session = dict(zip([d[0] for d in cur.description], row))

        cur.execute(
            "SELECT number, name, reps, duration_seconds, notes "
            "FROM warmups WHERE session_id = %s ORDER BY number",
            (session_id,),
        )
        session["warmup"] = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]

        cur.execute(
            "SELECT number, name, reps, duration_seconds, notes "
            "FROM cooldowns WHERE session_id = %s ORDER BY number",
            (session_id,),
        )
        session["cooldown"] = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]

        cur.execute(
            """
            SELECT id, number, name, tags, modality, movement_pattern,
                   notes, warmup_notes, form_cues,
                   goal_weight_kg, goal_sets, goal_rep_min, goal_rep_max, goal_rest_min,
                   goal_rest_seconds, goal_distance_meters, goal_target_duration_sec,
                   target_muscle_groups, rep_tempo
            FROM exercises WHERE session_id = %s ORDER BY number
            """,
            (session_id,),
        )
        exercises = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]

        for exercise in exercises:
            exercise_id = exercise.pop("id")

            cur.execute(
                """
                SELECT number, weight_kg, reps_full, reps_partial,
                       left_reps_full, left_reps_partial, right_reps_full, right_reps_partial,
                       rpe, rep_quality, rest_minutes, rest_seconds,
                       duration_seconds, distance_meters, heart_rate_bpm,
                       notes, failure_technique
                FROM working_sets WHERE exercise_id = %s ORDER BY number
                """,
                (exercise_id,),
            )
            exercise["sets"] = [
                dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT number, weight_kg, rep_count, notes
                FROM warmup_sets WHERE exercise_id = %s ORDER BY number
                """,
                (exercise_id,),
            )
            exercise["warmup_sets"] = [
                dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()
            ]

        session["exercises"] = exercises

    return session


def get_exercise_history(conn: Connection, name: str) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                s.date,
                s.phase,
                s.week,
                s.session_id,
                ws.number,
                ws.weight_kg,
                ws.reps_full,
                ws.reps_partial,
                ws.rpe,
                ws.rep_quality,
                ws.failure_technique
            FROM working_sets ws
            JOIN exercises e ON e.id = ws.exercise_id
            JOIN sessions s ON s.session_id = e.session_id
            WHERE LOWER(e.name) = LOWER(%s)
            ORDER BY s.date ASC, ws.number ASC
            """,
            (name,),
        )
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

    return [dict(zip(cols, row)) for row in rows]


def get_raw_input(conn: Connection, raw_input_id: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, content, source_kind, source_file, checksum, captured_at
            FROM raw_inputs WHERE id = %s
            """,
            (raw_input_id,),
        )
        row = cur.fetchone()
    if row is None:
        return None
    keys = ("id", "content", "source_kind", "source_file", "checksum", "captured_at")
    return dict(zip(keys, row))


def find_raw_inputs_by_checksum(conn: Connection, checksum: str) -> list[dict]:
    """Every capture of identical text, oldest first. Storage does not deduplicate (see
    insert_raw_input); this is how the ingest path can notice it has seen a file before."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, source_kind, source_file, captured_at
            FROM raw_inputs WHERE checksum = %s ORDER BY captured_at
            """,
            (checksum,),
        )
        rows = cur.fetchall()
    keys = ("id", "source_kind", "source_file", "captured_at")
    return [dict(zip(keys, r)) for r in rows]


_EXTRACTION_COLUMNS = (
    "id", "raw_input_id", "model", "prompt_version", "extract",
    "uncertain_fields", "warnings", "status", "corrections", "created_at", "confirmed_at",
)


def get_extraction(conn: Connection, extraction_id: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {', '.join(_EXTRACTION_COLUMNS)} FROM extractions WHERE id = %s",
            (extraction_id,),
        )
        row = cur.fetchone()
    return dict(zip(_EXTRACTION_COLUMNS, row)) if row else None


def get_extractions_for_raw_input(conn: Connection, raw_input_id: str) -> list[dict]:
    """Every attempt at reading one input, newest first. More than one is normal -- a re-run
    with a better model or prompt is the reason the raw layer exists."""
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT {', '.join(_EXTRACTION_COLUMNS)} FROM extractions "
            "WHERE raw_input_id = %s ORDER BY created_at DESC",
            (raw_input_id,),
        )
        rows = cur.fetchall()
    return [dict(zip(_EXTRACTION_COLUMNS, r)) for r in rows]
