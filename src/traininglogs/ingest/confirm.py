"""confirm: extraction_id -> session_id.

Takes a human-confirmed (possibly corrected) extract and writes it as the normalized
session, closing out the extraction that produced it.
"""
from __future__ import annotations

from pathlib import Path

from psycopg2.extensions import connection as Connection

from traininglogs.agent.schemas import TrainingLogLLMExtract
from traininglogs.db.fetch import get_extraction
from traininglogs.db.insert import confirm_extraction, insert_session
from traininglogs.processor.processor import build_session_from_extract


def confirm(
    conn: Connection,
    extraction_id: str,
    final_extract: TrainingLogLLMExtract,
    md_path: Path,
    corrections: list[dict] | None = None,
    inputs_root: Path | None = None,
    source_file: str | None = None,
) -> str:
    """Build and insert the session from a confirmed extract, and mark the extraction that
    produced it confirmed.

    `final_extract` is what gets written -- it may differ from what the model first produced
    if corrections were applied along the way. `corrections` are recorded on the extraction
    row, not folded into the extract, so what the model said and what the person changed stay
    permanently separable (roadmap C7).

    `md_path` is still required: session_id hashing and program/phase/week inference are
    file-path derived today. Input with no file path is Phase 7's problem, not this one's.
    """
    if get_extraction(conn, extraction_id) is None:
        raise ValueError(f"no extraction with id {extraction_id!r}")

    session = build_session_from_extract(final_extract, md_path, inputs_root)

    if not insert_session(
        conn, session, source_file=source_file, extraction_id=extraction_id
    ):
        raise SystemExit(
            f"\nERROR: session_id '{session.session_id}' already exists in the DB.\n"
            f"The date in '{md_path.name}' is likely wrong. Fix it and re-run.\n"
        )

    confirm_extraction(conn, extraction_id, corrections=corrections)

    return session.session_id
