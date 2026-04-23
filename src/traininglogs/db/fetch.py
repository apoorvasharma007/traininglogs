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
            SELECT session_id, date, program, phase, week, focus, duration_minutes, is_deload_week
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
                   phase, week, is_deload_week, focus, duration_minutes, user_id, user_name
            FROM sessions WHERE session_id = %s
            """,
            (session_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        session = dict(zip([d[0] for d in cur.description], row))

        cur.execute(
            """
            SELECT id, number, name, notes, warmup_notes, form_cues,
                   goal_weight_kg, goal_sets, goal_rep_min, goal_rep_max, goal_rest_min,
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
                SELECT number, weight_kg, reps_full, reps_partial, rpe,
                       rep_quality, rest_minutes, notes, failure_technique
                FROM working_sets WHERE exercise_id = %s ORDER BY number
                """,
                (exercise_id,),
            )
            exercise["working_sets"] = [
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
