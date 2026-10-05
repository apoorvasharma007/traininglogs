"""manual: a session logged in the app -> a workout session, with no AI and no card.

Its input is the session as the phone sent it, stored as JSON (kind `manual`), so History, Progress
and the record of what was entered treat it like any other session. The phone names each session
with an id when it starts (`client_id`); sending the same session again (a retry after a dropped
connection) finds that input and returns the session already saved instead of saving it twice.
"""
from __future__ import annotations

import json
from typing import Any

from psycopg2.extensions import connection as Connection

from traininglogs.agent.schemas import TrainingLogLLMExtract
from traininglogs.db.fetch import get_input_by_client_id
from traininglogs.db.insert import insert_input, insert_session
from traininglogs.ingest.confirm import AlreadySaved, build_session_from_extract

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


def _session_for(conn: Connection, user_id: str, input_id: str) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id::text FROM workout_sessions WHERE user_id = %s AND input_id = %s", (user_id, input_id)
        )
        row = cur.fetchone()
    return row[0] if row else None


def save_manual_session(conn: Connection, user_id: str, session: dict[str, Any]) -> tuple[str, bool]:
    """Saves the session for `user_id`; returns its id and whether it was new (False for a repeated
    send)."""
    known = get_input_by_client_id(conn, user_id, session["client_id"])
    if known is not None:
        saved = _session_for(conn, user_id, known["id"])
        if saved is not None:
            return saved, False
        input_id, content = known["id"], known["content"]
    else:
        content = json.dumps(session, sort_keys=True, default=str)
        input_id = insert_input(conn, user_id, content, kind="manual", client_id=session["client_id"])

    workout = build_session_from_extract(to_extract(session), content)
    session_id = insert_session(
        conn, user_id, workout, input_id, program_workout_id=session.get("program_workout_id"),
        started_at=session.get("started_at"), ended_at=session.get("ended_at"),
    )
    if session_id is None:
        raise AlreadySaved(session["client_id"])
    return session_id, True
