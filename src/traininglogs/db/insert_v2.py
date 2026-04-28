import json

from psycopg2.extensions import connection as Connection

from traininglogs.models.models_v2 import TrainingSession


def insert_session(conn: Connection, session: TrainingSession) -> bool:
    """Insert a full training session and all child records.

    Returns True if inserted, False if session_id already existed (skipped).
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM sessions WHERE session_id = %s", (session.session_id,)
        )
        if cur.fetchone():
            return False

        cur.execute(
            """
            INSERT INTO sessions (
                session_id, date, program, program_author, program_length_weeks,
                phase, week, is_deload_week, focus, duration_minutes, user_id, user_name
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                session.session_id,
                session.date,
                session.program,
                session.program_author,
                session.program_length_weeks,
                session.phase,
                session.week,
                session.is_deload_week,
                session.focus,
                session.session_duration_minutes,
                session.user_id,
                session.user_name,
            ),
        )

        for exercise in session.exercises:
            goal = exercise.current_goal
            rep_range = goal.rep_range if goal else None

            cur.execute(
                """
                INSERT INTO exercises (
                    session_id, number, name, notes, warmup_notes, form_cues,
                    goal_weight_kg, goal_sets, goal_rep_min, goal_rep_max, goal_rest_min,
                    target_muscle_groups, rep_tempo
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    session.session_id,
                    exercise.number,
                    exercise.name,
                    exercise.notes,
                    exercise.warmup_notes,
                    exercise.form_cues,
                    goal.weight_kg if goal else None,
                    goal.sets if goal else None,
                    rep_range.min if rep_range else None,
                    rep_range.max if rep_range else None,
                    goal.rest_minutes if goal else None,
                    exercise.target_muscle_groups,
                    exercise.rep_tempo,
                ),
            )
            exercise_id = cur.fetchone()[0]

            for ws in exercise.working_sets or []:
                ft_json = (
                    json.dumps(ws.failure_technique.model_dump(mode="json"))
                    if ws.failure_technique is not None
                    else None
                )
                cur.execute(
                    """
                    INSERT INTO working_sets (
                        exercise_id, number, weight_kg, reps_full, reps_partial,
                        rpe, rep_quality, rest_minutes, notes, failure_technique
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        exercise_id,
                        ws.number,
                        ws.weight_kg,
                        ws.rep_count.full,
                        ws.rep_count.partial,
                        ws.rpe,
                        ws.rep_quality_assessment.value if ws.rep_quality_assessment else None,
                        ws.actual_rest_minutes,
                        ws.notes,
                        ft_json,
                    ),
                )

            for warmup in exercise.warmup_sets or []:
                cur.execute(
                    """
                    INSERT INTO warmup_sets (exercise_id, number, weight_kg, rep_count, notes)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        exercise_id,
                        warmup.number,
                        warmup.weight_kg,
                        warmup.rep_count,
                        warmup.notes,
                    ),
                )

    conn.commit()
    return True
