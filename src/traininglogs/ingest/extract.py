"""extract: raw_input_id -> extraction_id.

Runs the LLM calls against a captured input and saves one attempt at reading it, with
status 'pending'. Never blocks on a human -- confirming an extraction is a separate step
(see confirm.py), which is what lets this function run behind an HTTP endpoint as easily as
in a terminal loop.
"""
from __future__ import annotations

from psycopg2.extensions import connection as Connection

from traininglogs.agent.extraction import assemble
from traininglogs.agent.prompts import PROMPT_VERSION
from traininglogs.agent.providers import AnthropicProvider, ExtractionProvider
from traininglogs.db.fetch import get_extractions_for_raw_input, get_raw_input
from traininglogs.db.insert import insert_extraction


def extract(
    conn: Connection,
    raw_input_id: str,
    provider: ExtractionProvider | None = None,
    model: str | None = None,
) -> str:
    """Read a captured raw input and store one attempt at interpreting it.

    Idempotent: if `raw_input_id` already has a pending or confirmed extraction, that id is
    returned and no model is called. Re-running extract on an input that already has one must
    not spend money producing a second copy (roadmap D3) -- a rejected extraction does not
    count, since rejecting one is exactly how a person asks for another attempt.
    """
    existing = [
        row for row in get_extractions_for_raw_input(conn, raw_input_id)
        if row["status"] in ("pending", "confirmed")
    ]
    if existing:
        return existing[0]["id"]

    raw = get_raw_input(conn, raw_input_id)
    if raw is None:
        raise ValueError(f"no raw_input with id {raw_input_id!r}")

    provider = provider or AnthropicProvider()
    model = model or provider.model

    result = assemble(raw["content"], provider=provider)

    return insert_extraction(
        conn,
        raw_input_id=raw_input_id,
        model=model,
        prompt_version=PROMPT_VERSION,
        extract=result.model_dump(mode="json"),
        uncertain_fields=list(result.uncertain_fields or []),
        warnings=list(result.warnings or []),
        status="pending",
    )
