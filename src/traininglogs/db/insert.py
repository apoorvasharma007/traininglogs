import hashlib
import json
import uuid

from psycopg2.extensions import connection as Connection

from traininglogs.models.models import Rest, TrainingSession, WorkingSet


def content_checksum(content: str) -> str:
    """sha256 of a raw input's text. Recognises text already captured without comparing whole
    documents, and proves the stored row was not altered afterwards."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def insert_raw_input(
    conn: Connection,
    content: str,
    source_kind: str = "markdown",
    source_file: str | None = None,
    raw_input_id: str | None = None,
) -> str:
    """Store what the person actually wrote, and return its id.

    Deliberately not deduplicated on checksum. Logging the same text twice is a real thing a
    person does -- repeating a session, re-importing a file -- and collapsing those would make
    two captures indistinguishable from one. The checksum is indexed so *finding* duplicates is
    a query; deciding what to do about them belongs to the ingest path, not to storage."""
    new_id = raw_input_id or uuid.uuid4().hex
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw_inputs (id, content, source_kind, source_file, checksum)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (new_id, content, source_kind, source_file, content_checksum(content)),
        )
    conn.commit()
    return new_id


def insert_extraction(
    conn: Connection,
    raw_input_id: str,
    model: str,
    prompt_version: str,
    extract: dict,
    uncertain_fields: list[str] | None = None,
    warnings: list[str] | None = None,
    status: str = "pending",
    corrections: list[dict] | None = None,
    extraction_id: str | None = None,
) -> str:
    """Store one attempt at reading a raw input, and return its id.

    `uncertain_fields` and `warnings` are stored alongside the extract rather than folded into
    it, because they are statements *about* the extraction rather than part of it -- and because
    they were previously computed and then dropped on the way to the normalized tables, leaving
    no record of how much to trust a row."""
    new_id = extraction_id or uuid.uuid4().hex
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO extractions (
                id, raw_input_id, model, prompt_version, extract,
                uncertain_fields, warnings, status, corrections, confirmed_at
            )
            -- confirmed_at follows from status rather than being a second thing to remember.
            -- Two fields that must agree, set independently, eventually disagree.
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                    CASE WHEN %s = 'confirmed' THEN now() ELSE NULL END)
            """,
            (
                new_id,
                raw_input_id,
                model,
                prompt_version,
                json.dumps(extract),
                uncertain_fields or [],
                warnings or [],
                status,
                json.dumps(corrections or []),
                status,
            ),
        )
    conn.commit()
    return new_id


def confirm_extraction(
    conn: Connection,
    extraction_id: str,
    corrections: list[dict] | None = None,
) -> None:
    """Mark an extraction confirmed, and record what changed to get there.

    status and confirmed_at are set in the same statement rather than left for the caller to
    keep in agreement -- the same reasoning as insert_extraction's CASE WHEN."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE extractions
            SET status = 'confirmed', confirmed_at = now(), corrections = %s
            WHERE id = %s
            """,
            (json.dumps(corrections or []), extraction_id),
        )
    conn.commit()


def _rest_minutes(rest: Rest | None) -> float | None:
    return rest.minutes if rest is not None else None


def _rest_seconds(rest: Rest | None) -> int | None:
    return rest.seconds if rest is not None else None


def insert_session(
    conn: Connection,
    session: TrainingSession,
    source_file: str | None = None,
    extraction_id: str | None = None,
) -> bool:
    """Insert a full training session and all child records.

    Returns True if inserted, False if session_id already existed (skipped).

    `source_file` and `extraction_id` are written here rather than patched in afterwards. They
    used to be the caller's job: the rules path ran an UPDATE after inserting, and the AI path
    simply never did, so every AI-parsed session in the database has no link to the text it came
    from. Two callers, one of which forgot, is the failure mode a parameter removes.
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
                weight_unit, user_id, user_name, notes, source_file, extraction_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                session.notes,
                source_file,
                extraction_id,
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
