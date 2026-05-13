import json

from psycopg2.extensions import connection as Connection

from traininglogs.models.models import Rest, TrainingSession, WorkingSet


def _rest_minutes(rest: Rest | None) -> float | None:
    return rest.minutes if rest is not None else None


def _rest_seconds(rest: Rest | None) -> int | None:
    return rest.seconds if rest is not None else None


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
                phase, week, is_deload_week, focus, duration_minutes,
                weight_unit, user_id, user_name
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                session.weight_unit,
                session.user_id,
                session.user_name,
            ),
        )

        for movement in session.warmup or []:
            cur.execute(
                """
                INSERT INTO warmups
                    (session_id, number, name, reps, duration_seconds, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    session.session_id,
                    movement.number,
                    movement.name,
                    movement.reps,
                    movement.duration_seconds,
                    movement.notes,
                ),
            )

        for movement in session.cooldown or []:
            cur.execute(
                """
                INSERT INTO cooldowns
                    (session_id, number, name, reps, duration_seconds, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    session.session_id,
                    movement.number,
                    movement.name,
                    movement.reps,
                    movement.duration_seconds,
                    movement.notes,
                ),
            )

        for exercise in session.exercises:
            goal = exercise.current_goal
            rep_range = goal.rep_range if goal else None

            cur.execute(
                """
                INSERT INTO exercises (
                    session_id, number, name,
                    tags, modality, movement_pattern,
                    notes, warmup_notes, form_cues,
                    goal_weight_kg, goal_sets, goal_rep_min, goal_rep_max,
                    goal_rest_min, goal_rest_seconds,
                    goal_distance_meters, goal_target_duration_sec,
                    target_muscle_groups, rep_tempo
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    session.session_id,
                    exercise.number,
                    exercise.name,
                    exercise.tags,
                    exercise.modality,
                    exercise.movement_pattern,
                    exercise.notes,
                    exercise.warmup_notes,
                    exercise.form_cues,
                    goal.weight_kg if goal else None,
                    goal.sets if goal else None,
                    rep_range.min if rep_range else None,
                    rep_range.max if rep_range else None,
                    _rest_minutes(goal.rest if goal else None),
                    _rest_seconds(goal.rest if goal else None),
                    goal.distance_meters if goal else None,
                    goal.target_duration_seconds if goal else None,
                    exercise.target_muscle_groups,
                    exercise.rep_tempo,
                ),
            )
            exercise_id = cur.fetchone()[0]

            for ws in exercise.sets or []:
                rc = ws.rep_count
                uni = ws.unilateral_rep_count
                ft_json = (
                    json.dumps(ws.failure_technique.model_dump(mode="json"))
                    if ws.failure_technique is not None
                    else None
                )
                cur.execute(
                    """
                    INSERT INTO working_sets (
                        exercise_id, number,
                        weight_kg, reps_full, reps_partial,
                        left_reps_full, left_reps_partial,
                        right_reps_full, right_reps_partial,
                        rpe, rep_quality, rest_minutes, rest_seconds,
                        duration_seconds, distance_meters, heart_rate_bpm,
                        notes, failure_technique
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        exercise_id,
                        ws.number,
                        ws.weight_kg,
                        rc.full if rc else None,
                        rc.partial if rc else None,
                        uni.left.full if uni and uni.left else None,
                        uni.left.partial if uni and uni.left else None,
                        uni.right.full if uni and uni.right else None,
                        uni.right.partial if uni and uni.right else None,
                        ws.rpe,
                        ws.rep_quality_assessment.value if ws.rep_quality_assessment else None,
                        _rest_minutes(ws.rest),
                        _rest_seconds(ws.rest),
                        ws.duration_seconds,
                        ws.distance_meters,
                        ws.heart_rate_bpm,
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
