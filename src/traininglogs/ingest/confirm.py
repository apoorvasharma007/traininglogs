"""confirm: a confirmed card -> a workout session, and how any session's fields are filled in."""
from __future__ import annotations

import hashlib

from psycopg2.extensions import connection as Connection

from traininglogs.agent.schemas import TrainingLogLLMExtract
from traininglogs.db.fetch import get_card, get_input
from traininglogs.db.insert import confirm_card, insert_session
from traininglogs.models.models import TrainingSession


class AlreadySaved(Exception):
    """The person already has a session from this same text on this same day."""


def dedup_key(content: str, date_str: str) -> str:
    """The date and a fingerprint of the text: `YYYY-MM-DD-<6 hex>`. Whitespace that doesn't change
    what was written (retyping, line endings, a trailing newline) is ignored, so the same note
    confirmed twice for the same day is recognised. Unique per person, not across people."""
    fingerprint = hashlib.sha256(" ".join(content.split()).encode()).hexdigest()[:6]
    return f"{date_str}-{fingerprint}"


def build_session_from_extract(extract: TrainingLogLLMExtract, content: str) -> TrainingSession:
    """An extract as a TrainingSession. `content` is the input's text, which the dedup key (kept in
    the model's session_id) is made from."""
    session = extract.model_dump(mode="python", exclude={"uncertain_fields"})
    session["session_id"] = dedup_key(content, extract.date)
    # The model still requires these; they aren't stored. The owner is workout_sessions.user_id.
    session["user_id"] = "-"
    session["user_name"] = "-"
    session["data_model_version"] = "0.0.1"
    session["data_model_type"] = "TrainingSession"
    return TrainingSession.model_validate(session)


def confirm(
    conn: Connection,
    user_id: str,
    card_id: str,
    final_extract: TrainingLogLLMExtract,
    corrections: list[dict] | None = None,
    program_workout_id: str | None = None,
) -> str:
    """Save the confirmed (possibly corrected) reading as a session and mark the card confirmed;
    returns the session's id.

    `final_extract` is what gets saved; the card keeps the AI's own reading, and `corrections` the
    person's changes, so the two stay separate.
    """
    card = get_card(conn, user_id, card_id)
    if card is None:
        raise ValueError(f"no card with id {card_id!r}")
    note = get_input(conn, user_id, card["input_id"])
    session = build_session_from_extract(final_extract, note["content"])
    # The session and the card's confirmation commit together, so neither is ever left without the other.
    session_id = insert_session(
        conn, user_id, session, card["input_id"], card_id=card_id, program_workout_id=program_workout_id, commit=False
    )
    if session_id is None:
        raise AlreadySaved(card_id)
    confirm_card(conn, user_id, card_id, corrections)
    return session_id
