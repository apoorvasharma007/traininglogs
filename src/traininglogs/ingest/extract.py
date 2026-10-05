"""extract: a note -> a confirmation card.

Runs the AI on a stored note and saves its reading as a card with status 'pending'. Never waits on
a person: confirming is a separate step (confirm.py).
"""
from __future__ import annotations

from psycopg2.extensions import connection as Connection

from traininglogs.agent.extraction import assemble
from traininglogs.agent.prompts import PROMPT_VERSION
from traininglogs.agent.providers import AnthropicProvider, ExtractionProvider
from traininglogs.db.fetch import get_cards_for_input, get_input
from traininglogs.db.insert import insert_ai_calls, insert_card


def extract(
    conn: Connection,
    user_id: str,
    input_id: str,
    provider: ExtractionProvider | None = None,
    model: str | None = None,
) -> str:
    """Read a stored note and save the reading as a card; returns the card's id.

    Idempotent: a note that already has a pending or confirmed card returns that card with no AI
    call, so running this twice never pays twice. A rejected card doesn't count: rejecting one is
    how a person asks for another reading.
    """
    existing = [c for c in get_cards_for_input(conn, user_id, input_id) if c["status"] in ("pending", "confirmed")]
    if existing:
        return existing[0]["id"]

    note = get_input(conn, user_id, input_id)
    if note is None:
        raise ValueError(f"no input with id {input_id!r}")

    provider = provider or AnthropicProvider()
    model = model or provider.model

    print(f"[ingest] input_id={input_id} extract: starting")
    try:
        result = assemble(note["content"], provider=provider)
    finally:
        # Kept whether the reading worked or not: a run that fails partway still paid for its calls.
        calls = getattr(provider, "calls", [])
        insert_ai_calls(conn, user_id, input_id, calls)
    print(f"[ingest] input_id={input_id} extract: done, {len(calls)} AI call(s)")

    # The AI can only read a date out of the text. When the text has none, it flags "date" as
    # unsure instead of inventing one; the day the note was saved fills the gap, still flagged,
    # since "saved today" isn't the same as "trained today".
    if "date" in (result.uncertain_fields or []):
        result.date = note["created_at"].strftime("%Y-%m-%d")

    return insert_card(
        conn,
        user_id,
        input_id,
        model=model,
        prompt_version=PROMPT_VERSION,
        extract=result.model_dump(mode="json"),
        uncertain_fields=list(result.uncertain_fields or []),
        warnings=list(result.warnings or []),
    )
