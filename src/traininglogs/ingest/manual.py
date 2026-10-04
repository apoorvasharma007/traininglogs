"""manual: a session entered set by set in the app -> a confirmed session, with no model call.

It goes through the same three rows as a note the model reads -- a raw input (kind `manual`), an
extraction, the session -- so History, Progress and the correction log treat it like any other
session. The raw input's content is the request itself, as JSON: what the person produced.

The phone names each session with an id when it starts (`client_id`) and uses that id as the raw
input's id. Sending the same session again -- a retry after a dropped connection -- finds that
raw input and returns the session already saved instead of saving it twice.
"""
from __future__ import annotations

import json
from typing import Any

from psycopg2.extensions import connection as Connection

from traininglogs.agent.schemas import TrainingLogLLMExtract
from traininglogs.db.fetch import get_raw_input
from traininglogs.db.insert import insert_extraction, insert_raw_input
from traininglogs.db.programs import link_session_to_workout
from traininglogs.ingest.confirm import confirm

MANUAL_MODEL = "none"
MANUAL_PROMPT_VERSION = "manual"


def to_extract(session: dict[str, Any]) -> TrainingLogLLMExtract:
    """The request, in the shape every other session is written from."""
    exercises = []
    for n, ex in enumerate(session["exercises"], start=1):
        exercises.append({
            "number": n,
            "name": ex["name"],
            "notes": ex.get("notes") or None,
            "warmup_sets": [
                {"number": i, "weight_kg": w["weight_kg"], "rep_count": w.get("reps"), "notes": w.get("notes") or None}
                for i, w in enumerate(ex["warmup_sets"], start=1)
            ] or None,
            "sets": [
                {
                    "number": i,
                    "weight_kg": s.get("weight_kg"),
                    "rep_count": {"full": s["reps"], "partial": 0} if s.get("reps") is not None else None,
                    "rpe": s.get("rpe"),
                    "notes": s.get("notes") or None,
                }
                for i, s in enumerate(ex["sets"], start=1)
            ] or None,
        })
    return TrainingLogLLMExtract.model_validate({
        "date": session["date"],
        "focus": session.get("focus") or None,
        "is_deload_week": session.get("is_deload") or None,
        # A session under a minute arrives as 0; a session's duration must be positive, so it's left out.
        "session_duration_minutes": session.get("duration_minutes") or None,
        "notes": session.get("notes") or None,
        "warmup": _movements(session.get("warmup")),
        "cooldown": _movements(session.get("cooldown")),
        "exercises": exercises,
    })


def _movements(items: list[dict] | None) -> list[dict] | None:
    return [
        {"number": n, "name": m["name"], "reps": m.get("reps"), "duration_seconds": m.get("duration_seconds"),
         "notes": m.get("notes") or None}
        for n, m in enumerate(items or [], start=1)
    ] or None


def _saved_session_id(conn: Connection, raw_input_id: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.session_id FROM sessions s
            JOIN extractions e ON e.id = s.extraction_id
            WHERE e.raw_input_id = %s
            """,
            (raw_input_id,),
        )
        row = cur.fetchone()
    return row[0] if row else None


class ClientIdTaken(Exception):
    """The phone's id for the session already belongs to someone else's input."""


def save_manual_session(conn: Connection, session: dict[str, Any], user_id: str) -> tuple[str, bool]:
    """Saves the session for `user_id`; returns its id and whether it was new (False for a
    repeated send). The phone chooses `client_id`, so an id already used by another person is
    refused rather than answered with their session."""
    raw_input_id = session["client_id"]
    existing_input = get_raw_input(conn, raw_input_id)
    if existing_input is not None:
        if str(existing_input.get("user_id")) != user_id:
            raise ClientIdTaken(raw_input_id)
        existing = _saved_session_id(conn, raw_input_id)
        if existing is not None:
            return existing, False

    extract = to_extract(session)
    if existing_input is None:
        content = json.dumps(session, sort_keys=True, default=str)
        insert_raw_input(conn, content, source_kind="manual", raw_input_id=raw_input_id, user_id=user_id)
    extraction_id = insert_extraction(
        conn,
        raw_input_id=raw_input_id,
        model=MANUAL_MODEL,
        prompt_version=MANUAL_PROMPT_VERSION,
        extract=extract.model_dump(mode="json"),
        uncertain_fields=[],
        warnings=[],
        status="pending",
    )
    saved = confirm(conn, extraction_id, extract)
    if session.get("program_workout_id"):
        link_session_to_workout(conn, saved.session_id, session["program_workout_id"])
    return saved.session_id, True
