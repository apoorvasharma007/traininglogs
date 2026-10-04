"""confirm: extraction_id -> session_id.

Takes a human-confirmed (possibly corrected) extract and writes it as the normalized
session, closing out the extraction that produced it.
"""
from __future__ import annotations

import hashlib

from psycopg2.extensions import connection as Connection

from traininglogs.agent.schemas import TrainingLogLLMExtract
from traininglogs.db.fetch import get_extraction, get_raw_input
from traininglogs.db.insert import confirm_extraction, insert_session
from traininglogs.models.models import TrainingSession


def _normalize_content(content: str) -> str:
    """Collapse whitespace differences that don't change what was written -- so the same
    text, retyped, re-copied with different line endings, or resubmitted with a trailing
    newline, is recognised as the same input."""
    return " ".join(content.split())


def compute_session_id(content: str, date_str: str) -> str:
    """Deterministic session ID: YYYY-MM-DD-<6-char SHA256 of the normalized content>.

    Identity is the text: the same input submitted twice collides on this id and is caught by
    the session_id check in insert_session, with no separate dedup mechanism. Compare sessions
    on date, not session_id, when that matters: the scheme has changed before."""
    h = hashlib.sha256(_normalize_content(content).encode()).hexdigest()[:6]
    return f"{date_str}-{h}"


def build_session_from_extract(extract: TrainingLogLLMExtract, content: str) -> TrainingSession:
    """A confirmed extract as a TrainingSession, with the fields the extract doesn't produce.
    `content` is the captured text, which session_id is derived from."""
    session_dict = extract.model_dump(mode="python", exclude={"uncertain_fields"})
    session_dict["session_id"] = compute_session_id(content, extract.date)
    # The model still requires these; they aren't stored. The owner is sessions.user_id.
    session_dict["user_id"] = "-"
    session_dict["user_name"] = "-"
    session_dict["data_model_version"] = "0.0.1"
    session_dict["data_model_type"] = "TrainingSession"
    return TrainingSession.model_validate(session_dict)


def confirm(
    conn: Connection,
    extraction_id: str,
    final_extract: TrainingLogLLMExtract,
    corrections: list[dict] | None = None,
) -> TrainingSession:
    """Build and insert the session from a confirmed extract, and mark the extraction that
    produced it confirmed.

    `final_extract` is what gets written -- it may differ from what the model first produced
    if corrections were applied along the way. `corrections` are recorded on the extraction
    row, not folded into the extract, so what the model said and what the person changed stay
    permanently separable (roadmap C7).

    """
    extraction = get_extraction(conn, extraction_id)
    if extraction is None:
        raise ValueError(f"no extraction with id {extraction_id!r}")

    raw = get_raw_input(conn, extraction["raw_input_id"])
    if raw is None:
        raise ValueError(f"no raw_input for extraction {extraction_id!r}")

    session = build_session_from_extract(final_extract, raw["content"])

    if not insert_session(conn, session, extraction_id=extraction_id):
        raise SystemExit(
            f"\nERROR: session_id '{session.session_id}' already exists in the DB.\n"
            f"The date is likely wrong, or this exact content was already confirmed. Fix "
            f"the date and re-run.\n"
        )

    confirm_extraction(conn, extraction_id, corrections=corrections)

    return session
