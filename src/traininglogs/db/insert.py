import json
from psycopg2.extensions import connection as Connection


def insert_session(conn: Connection, session: dict) -> None:
    """Insert a full training session and all child records. Skips if session_id already exists."""
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM sessions WHERE session_id = %s", (session["session_id"],))
        if cur.fetchone():
            return

        cur.execute(
            """
            INSERT INTO sessions (
                session_id, date, program, program_author, program_length_weeks,
                phase, week, is_deload_week, focus, duration_minutes, user_name
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                session["session_id"],
                session["date"],
                session.get("program"),
                session.get("program_author"),
                session.get("program_length_weeks"),
                session.get("phase"),
                session.get("week"),
                session.get("is_deload_week"),
                session.get("focus"),
                session.get("session_duration_minutes"),
                session.get("user_name"),
            ),
        )

        for exercise in session.get("exercises", []):
            goal = exercise.get("current_goal") or {}
            rep_range = goal.get("rep_range") or {}

            cur.execute(
                """
                INSERT INTO exercises (
                    session_id, number, name, notes, warmup_notes, form_cues,
                    goal_weight_kg, goal_sets, goal_rep_min, goal_rep_max, goal_rest_min
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    session["session_id"],
                    exercise.get("number"),
                    exercise["name"],
                    exercise.get("notes"),
                    exercise.get("warmup_notes"),
                    exercise.get("form_cues"),
                    goal.get("weight_kg"),
                    goal.get("sets"),
                    rep_range.get("min"),
                    rep_range.get("max"),
                    goal.get("rest_minutes"),
                ),
            )
            exercise_id = cur.fetchone()[0]

            for ws in exercise.get("working_sets", []):
                rep_count = ws.get("rep_count") or {}
                cur.execute(
                    """
                    INSERT INTO working_sets (
                        exercise_id, number, weight_kg, reps_full, reps_partial,
                        rpe, rep_quality, rest_minutes, notes, failure_technique
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        exercise_id,
                        ws.get("number"),
                        ws.get("weight_kg"),
                        rep_count.get("full") if isinstance(rep_count, dict) else rep_count,
                        rep_count.get("partial", 0) if isinstance(rep_count, dict) else 0,
                        ws.get("rpe"),
                        ws.get("rep_quality_assessment"),
                        ws.get("actual_rest_minutes"),
                        ws.get("notes"),
                        json.dumps(ws["failure_technique"]) if ws.get("failure_technique") else None,
                    ),
                )

            for warmup in [w for w in (exercise.get("warmup_sets") or []) if w is not None]:
                cur.execute(
                    """
                    INSERT INTO warmup_sets (exercise_id, number, weight_kg, rep_count, notes)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        exercise_id,
                        warmup.get("number"),
                        warmup.get("weight_kg"),
                        warmup.get("rep_count"),
                        warmup.get("notes"),
                    ),
                )

    conn.commit()
