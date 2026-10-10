"""Writing people's data. Every function takes the owner (users.id) and every row it writes carries
it; the database refuses a row whose owner differs from its parent's (schema.sql)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from psycopg2.extensions import connection as Connection
from psycopg2.extras import execute_values

from traininglogs.db.ids import new_id
from traininglogs.models.models import Rest, TrainingSession


def content_checksum(content: str) -> str:
    """sha256 of an input's text: proves the stored row wasn't altered afterwards."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def insert_input(
    conn: Connection,
    user_id: str,
    content: str,
    kind: str = "text",
    client_id: str | None = None,
    source: str | None = None,
) -> str:
    """Store what the person wrote or entered, exactly as given, and return its id.

    Not deduplicated on checksum: logging the same text twice is a real thing a person does.
    An app session's `client_id` is unique per person, which is how a resend is recognised."""
    input_id = new_id()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO input_text (id, user_id, content, kind, client_id, checksum, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (input_id, user_id, content, kind, client_id, content_checksum(content), source),
        )
    conn.commit()
    return input_id


def insert_card(
    conn: Connection,
    user_id: str,
    input_id: str,
    model: str,
    prompt_version: str,
    extract: dict,
    uncertain_fields: list[str] | None = None,
    warnings: list[str] | None = None,
    status: str = "pending",
) -> str:
    """Store the AI's reading of a note as a confirmation card, and return its id.

    `uncertain_fields` and `warnings` sit beside the extract rather than inside it: they're
    statements about the reading, not part of it."""
    card_id = new_id()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO input_text_confirmation_cards (
                id, user_id, input_id, model, prompt_version, extract,
                uncertain_fields, warnings, status, confirmed_at
            )
            -- confirmed_at follows from status rather than being a second thing to keep in step.
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CASE WHEN %s = 'confirmed' THEN now() END)
            """,
            (
                card_id, user_id, input_id, model, prompt_version, json.dumps(extract),
                uncertain_fields or [], warnings or [], status, status,
            ),
        )
    conn.commit()
    return card_id


def insert_ai_calls(conn: Connection, user_id: str, input_id: str, calls: list[dict]) -> None:
    """Keep the record of each paid AI call made for one input, whether it worked or not (a failed
    call still cost money). `calls` is what a provider collects in `.calls`; none is a normal no-op."""
    if not calls:
        return
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO ai_call_logs (
                id, user_id, input_id, step, model, attempts, input_tokens, output_tokens,
                cost_usd, ms, cached, failed, raw_payload
            ) VALUES %s
            """,
            [
                (
                    new_id(), user_id, input_id, c["step"], c["model"], c["attempts"],
                    c.get("input_tokens", 0), c.get("output_tokens", 0), c.get("cost_usd", 0), c["ms"],
                    c.get("cached", False), c.get("failed"),
                    json.dumps(c["raw_payload"]) if c.get("raw_payload") is not None else None,
                )
                for c in calls
            ],
        )
    conn.commit()


def confirm_card(conn: Connection, user_id: str, card_id: str, corrections: list[dict] | None = None) -> bool:
    """Mark a pending card confirmed, with what changed to get there; False if it isn't pending.
    Leaves the commit to the caller. A second confirm at the same moment waits for the first to
    finish, then finds the card no longer pending."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE input_text_confirmation_cards
            SET status = 'confirmed', confirmed_at = now(), corrections = %s
            WHERE id = %s AND user_id = %s AND status = 'pending'
            """,
            (json.dumps(corrections or []), card_id, user_id),
        )
        return cur.rowcount == 1


def name_key(name: str) -> str:
    """An exercise name ignoring case and extra spaces; matches user_exercises.name_key."""
    return " ".join(name.split()).lower()


def user_exercise_ids(cur, user_id: str, names: list[str]) -> dict[str, str]:
    """The person's exercise id for each name, by name_key, making the ones they haven't used yet.
    A new one links to a shared exercise when the name is that exercise's name or one of its other
    names. Two queries for the whole session, however many exercises it has."""
    wanted = {name_key(n): n.strip() for n in names if n.strip()}
    if not wanted:
        return {}
    cur.execute(
        "SELECT name_key, id FROM user_exercises WHERE user_id = %s AND name_key = ANY(%s)",
        (user_id, list(wanted)),
    )
    found = {key: str(i) for key, i in cur.fetchall()}
    missing = [(new_id(), user_id, wanted[key], key) for key in wanted if key not in found]
    if missing:
        execute_values(
            cur,
            """
            INSERT INTO user_exercises (id, user_id, name, exercise_id)
            SELECT v.id::uuid, v.user_id::uuid, v.name,
                   (SELECT e.id FROM exercises e WHERE lower(e.name) = v.key OR v.key = ANY(e.other_names) LIMIT 1)
            FROM (VALUES %s) AS v (id, user_id, name, key)
            ON CONFLICT (user_id, name_key) DO NOTHING
            """,
            missing,
        )
        cur.execute(
            "SELECT name_key, id FROM user_exercises WHERE user_id = %s AND name_key = ANY(%s)",
            (user_id, list(wanted)),
        )
        found = {key: str(i) for key, i in cur.fetchall()}
    return found


def _rest_minutes(rest: Rest | None) -> float | None:
    return rest.minutes if rest is not None else None


def _rest_seconds(rest: Rest | None) -> int | None:
    return rest.seconds if rest is not None else None


def insert_session(
    conn: Connection,
    user_id: str,
    session: TrainingSession,
    input_id: str,
    card_id: str | None = None,
    program_workout_id: str | None = None,
    source: str | None = None,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    commit: bool = True,
) -> str | None:
    """Save a whole session for `user_id` and return its id, or None when the person already has
    a session with the same dedup key (session.session_id: the date and a fingerprint of the
    input's text), so nothing is saved twice. All of it or none; `commit=False` leaves it in the
    caller's transaction, and on None the caller decides what to undo."""
    session_id = new_id()
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO workout_sessions (
                id, user_id, date, started_at, ended_at, duration_minutes, focus, notes, dedup_key,
                input_id, confirmation_card_id, program_workout_id, program, program_author,
                program_length_weeks, phase, week, is_deload_week, weight_unit, source
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, dedup_key) DO NOTHING
            RETURNING id
            """,
            (
                session_id, user_id, session.date, started_at, ended_at, session.session_duration_minutes,
                session.focus, session.notes, session.session_id, input_id, card_id, program_workout_id, session.program,
                session.program_author, session.program_length_weeks, session.phase, session.week,
                session.is_deload_week, session.weight_unit, source,
            ),
        )
        if cur.fetchone() is None:
            return None

        movements = {"workout_session_warmups": session.warmup, "workout_session_cooldowns": session.cooldown}
        for table, items in movements.items():
            if items:
                execute_values(
                    cur,
                    f"INSERT INTO {table} (id, user_id, session_id, position, name, reps, duration_seconds, notes) VALUES %s",
                    [(new_id(), user_id, session_id, m.number, m.name, m.reps, m.duration_seconds, m.notes) for m in items],
                )

        exercise_ids = user_exercise_ids(cur, user_id, [e.name for e in session.exercises])
        exercise_rows, set_rows = [], []
        for exercise in session.exercises:
            row_id = new_id()
            goal = exercise.current_goal
            rep_range = goal.rep_range if goal else None
            exercise_rows.append((
                row_id, user_id, session_id, exercise.number, exercise_ids[name_key(exercise.name)],
                exercise.name, exercise.notes, exercise.warmup_notes, exercise.tags, exercise.modality,
                exercise.movement_pattern, exercise.form_cues, exercise.target_muscle_groups, exercise.rep_tempo,
                goal.weight_kg if goal else None, goal.sets if goal else None,
                rep_range.min if rep_range else None, rep_range.max if rep_range else None,
                _rest_minutes(goal.rest if goal else None), _rest_seconds(goal.rest if goal else None),
                goal.distance_meters if goal else None, goal.target_duration_seconds if goal else None,
            ))
            for w in exercise.warmup_sets or []:
                set_rows.append((
                    new_id(), user_id, row_id, w.number, "warmup", w.weight_kg, w.rep_count, None,
                    None, None, None, None, None, None, None, None, None, None, None, w.notes, None,
                ))
            for s in exercise.sets or []:
                rc, uni = s.rep_count, s.unilateral_rep_count
                set_rows.append((
                    new_id(), user_id, row_id, s.number, "working", s.weight_kg,
                    rc.full if rc else None, rc.partial if rc else None,
                    uni.left.full if uni and uni.left else None, uni.left.partial if uni and uni.left else None,
                    uni.right.full if uni and uni.right else None, uni.right.partial if uni and uni.right else None,
                    s.rpe, s.rep_quality_assessment.value if s.rep_quality_assessment else None,
                    _rest_minutes(s.rest), _rest_seconds(s.rest), s.duration_seconds, s.distance_meters,
                    s.heart_rate_bpm, s.notes,
                    json.dumps(s.failure_technique.model_dump(mode="json")) if s.failure_technique else None,
                ))
        execute_values(
            cur,
            """
            INSERT INTO workout_session_exercises (
                id, user_id, session_id, position, user_exercise_id, name, notes, warmup_notes, tags,
                modality, movement_pattern, form_cues, target_muscle_groups, rep_tempo, goal_weight_kg,
                goal_sets, goal_rep_min, goal_rep_max, goal_rest_min, goal_rest_seconds,
                goal_distance_meters, goal_target_duration_sec
            ) VALUES %s
            """,
            exercise_rows,
        )
        if set_rows:
            execute_values(
                cur,
                """
                INSERT INTO workout_session_sets (
                    id, user_id, exercise_id, position, kind, weight_kg, reps_full, reps_partial,
                    left_reps_full, left_reps_partial, right_reps_full, right_reps_partial, rpe,
                    rep_quality, rest_minutes, rest_seconds, duration_seconds, distance_meters,
                    heart_rate_bpm, notes, failure_technique
                ) VALUES %s
                """,
                set_rows,
            )
    if commit:
        conn.commit()
    return session_id


def set_key_lifts(conn: Connection, user_id: str, names: list[str]) -> None:
    """Saves the lifts the person wants first in Progress, in their order."""
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET key_lifts = %s, updated_at = now() WHERE id = %s", (names, user_id))
    conn.commit()


def insert_feedback(conn: Connection, user_id: str, kind: str, message: str, app_version: str | None) -> str:
    """Saves a message sent from Settings; returns its id."""
    feedback_id = new_id()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO feedback (id, user_id, kind, message, app_version) VALUES (%s, %s, %s, %s, %s)",
            (feedback_id, user_id, kind, message, app_version),
        )
    conn.commit()
    return feedback_id
