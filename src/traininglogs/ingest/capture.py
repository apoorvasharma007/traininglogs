"""capture: text -> raw_input_id.

The one call site cli/ and api/ share for turning what a person wrote into a stored row --
so neither can start capturing text without the other noticing the shape changed.
"""
from __future__ import annotations

from psycopg2.extensions import connection as Connection

from traininglogs.db.insert import insert_raw_input


def capture(
    conn: Connection,
    content: str,
    source_kind: str = "markdown",
    source_file: str | None = None,
) -> str:
    """Store what the person actually wrote, before anything is asked of a model.

    Returns the raw_input_id. Deliberately does nothing else -- no LLM call, no git, no
    dashboard -- so a capture always succeeds even if everything downstream of it fails.
    """
    return insert_raw_input(conn, content, source_kind=source_kind, source_file=source_file)
