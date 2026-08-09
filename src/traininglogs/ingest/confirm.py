"""confirm: extraction_id -> session_id.

Takes a human-confirmed (possibly corrected) extract and writes it as the normalized
session, closing out the extraction that produced it.
"""
from __future__ import annotations

from pathlib import Path

from psycopg2.extensions import connection as Connection

from traininglogs.agent.schemas import TrainingLogLLMExtract
from traininglogs.db.fetch import get_extraction, get_raw_input
from traininglogs.db.insert import confirm_extraction, insert_session
from traininglogs.models.models import TrainingSession
from traininglogs.processor.processor import build_session_from_extract


def confirm(
    conn: Connection,
    extraction_id: str,
    final_extract: TrainingLogLLMExtract,
    md_path: Path | None = None,
    corrections: list[dict] | None = None,
    inputs_root: Path | None = None,
    source_file: str | None = None,
) -> TrainingSession:
    """Build and insert the session from a confirmed extract, and mark the extraction that
    produced it confirmed.

    `final_extract` is what gets written -- it may differ from what the model first produced
    if corrections were applied along the way. `corrections` are recorded on the extraction
    row, not folded into the extract, so what the model said and what the person changed stay
    permanently separable (roadmap C7).

    `md_path` is optional: session_id is derived from the captured content itself (see
    `processor.compute_session_id`), fetched here from the raw input the extraction came
    from, so this works the same whether the caller has a file (`cli/log.py`) or not (the
    API). `md_path`, when given, only adds program/phase/week from the file's directory
    position.
    """
    extraction = get_extraction(conn, extraction_id)
    if extraction is None:
        raise ValueError(f"no extraction with id {extraction_id!r}")

    raw = get_raw_input(conn, extraction["raw_input_id"])
    if raw is None:
        raise ValueError(f"no raw_input for extraction {extraction_id!r}")

    session = build_session_from_extract(final_extract, raw["content"], md_path, inputs_root)

    if not insert_session(
        conn, session, source_file=source_file, extraction_id=extraction_id
    ):
        raise SystemExit(
            f"\nERROR: session_id '{session.session_id}' already exists in the DB.\n"
            f"The date is likely wrong, or this exact content was already confirmed. Fix "
            f"the date and re-run.\n"
        )

    confirm_extraction(conn, extraction_id, corrections=corrections)

    return session
