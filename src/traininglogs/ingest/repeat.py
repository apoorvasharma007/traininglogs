"""repeat: a stored session -> a new pending extraction, with no LLM call.

The person picks a past session to train again; this builds a card from it that goes through
the normal edit/confirm path. It reads the normalized tables (`get_session`), so it works the
same for a session logged through the app and one imported from markdown before extractions
existed.

What carries over is the plan: exercises, goals, and each set's weight and reps. What doesn't
is how that day went -- RPE, quality, failure technique, rest, heart rate, duration -- and
every note: a note belongs to the day it was written, so the UI shows the source session's
notes as "last time" instead of copying them in (roadmap Phase 5b Step 7).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from psycopg2.extensions import connection as Connection

from traininglogs.agent.schemas import TrainingLogLLMExtract
from traininglogs.db.fetch import get_session
from traininglogs.db.insert import insert_extraction, insert_raw_input

REPEAT_MODEL = "none"
REPEAT_PROMPT_VERSION = "repeat"


def _rep_count(full: int | None, partial: int | None) -> dict | None:
    return None if full is None else {"full": full, "partial": partial or 0}


def _goal(ex: dict) -> dict | None:
    rep_min, rep_max = ex["goal_rep_min"], ex["goal_rep_max"]
    if rep_min is None or rep_max is None:
        rep_min = rep_max = rep_min if rep_min is not None else rep_max
    rest = None
    if ex["goal_rest_min"] is not None:
        rest = {"minutes": ex["goal_rest_min"]}
    elif ex["goal_rest_seconds"] is not None:
        rest = {"seconds": ex["goal_rest_seconds"]}
    goal = {
        "weight_kg": ex["goal_weight_kg"],
        "sets": ex["goal_sets"],
        "rep_range": {"min": rep_min, "max": rep_max} if rep_min is not None else None,
        "rest": rest,
        "distance_meters": ex["goal_distance_meters"],
        "target_duration_seconds": ex["goal_target_duration_sec"],
    }
    return goal if any(v is not None for v in goal.values()) else None


def _working_set(ws: dict) -> dict:
    left = _rep_count(ws["left_reps_full"], ws["left_reps_partial"])
    right = _rep_count(ws["right_reps_full"], ws["right_reps_partial"])
    return {
        "number": ws["number"],
        "weight_kg": ws["weight_kg"],
        "rep_count": _rep_count(ws["reps_full"], ws["reps_partial"]),
        "unilateral_rep_count": {"left": left, "right": right} if left or right else None,
        "duration_seconds": ws["duration_seconds"],
        "distance_meters": ws["distance_meters"],
    }


def _exercise(ex: dict) -> dict:
    return {
        "number": ex["number"],
        "name": ex["name"],
        "tags": ex["tags"],
        "modality": ex["modality"],
        "movement_pattern": ex["movement_pattern"],
        "form_cues": ex["form_cues"],
        "target_muscle_groups": ex["target_muscle_groups"],
        "rep_tempo": ex["rep_tempo"],
        "current_goal": _goal(ex),
        "warmup_sets": [
            {"number": w["number"], "weight_kg": w["weight_kg"], "rep_count": w["rep_count"]}
            for w in ex["warmup_sets"]
        ] or None,
        "sets": [_working_set(ws) for ws in ex["sets"]] or None,
    }


def _movement(m: dict) -> dict:
    return {
        "number": m["number"],
        "name": m["name"],
        "reps": m["reps"],
        "duration_seconds": m["duration_seconds"],
    }


def session_to_extract(session: dict[str, Any], date: str) -> TrainingLogLLMExtract:
    """Build a new extract from a stored session (as `get_session` returns it), dated `date`.

    `date` is flagged uncertain: it is when the repeat was started, which is not necessarily
    when the workout happened -- the same reason extraction flags a date it had to default.
    """
    return TrainingLogLLMExtract.model_validate({
        "date": date,
        "program": session["program"],
        "phase": session["phase"],
        "week": session["week"],
        "is_deload_week": session["is_deload_week"],
        "focus": session["focus"],
        "warmup": [_movement(m) for m in session["warmup"]] or None,
        "cooldown": [_movement(m) for m in session["cooldown"]] or None,
        "exercises": [_exercise(ex) for ex in session["exercises"]],
        "uncertain_fields": ["date"],
    })


def repeat_session(
    conn: Connection, session_id: str, user_id: str, now: datetime | None = None
) -> tuple[str, str] | None:
    """Write a raw input and a pending extraction repeating `session_id`; return their ids,
    or None if there is no such session.

    The raw input's content is one line naming the source, when the repeat started, and the
    raw input's own id. The id is what keeps every repeat's content -- and so the session_id it
    confirms into, which is derived from content -- unique: repeating the same session twice
    in a day doesn't collide, however close together. A timestamp alone wouldn't guarantee
    that.
    """
    session = get_session(conn, session_id)
    if session is None:
        return None

    now = now or datetime.now(timezone.utc)
    extract = session_to_extract(session, now.date().isoformat())
    raw_input_id = uuid.uuid4().hex
    content = (
        f"Repeat of {session_id} ({session['focus'] or 'session'}, {session['date']}), "
        f"started {now.isoformat(timespec='seconds')} [{raw_input_id}]"
    )
    insert_raw_input(
        conn, content, source_kind="manual", source_file=session_id, raw_input_id=raw_input_id,
        user_id=user_id,
    )
    extraction_id = insert_extraction(
        conn,
        raw_input_id=raw_input_id,
        model=REPEAT_MODEL,
        prompt_version=REPEAT_PROMPT_VERSION,
        extract=extract.model_dump(mode="json"),
        uncertain_fields=list(extract.uncertain_fields),
        warnings=[],
        status="pending",
    )
    return raw_input_id, extraction_id
