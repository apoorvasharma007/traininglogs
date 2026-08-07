"""Integration tests for the capture and interpretation layers (`raw_inputs`, `extractions`).

Real Postgres, per the project's testing rules — a mocked database would pass while the actual
constraints, defaults and cascades were wrong, which is most of what these tables are.

What these two tables are for: an extraction is derived from a raw input, so it must be possible
to derive it again — with a better model, a fixed prompt, a second reading — without asking the
person to write anything twice. That is why a raw input can have many extractions, and why the
raw text is stored whole rather than only its parsed result.
"""
from __future__ import annotations

import os

import psycopg2
import pytest

from traininglogs.db.db import apply_schema, get_connection
from traininglogs.db.fetch import (
    find_raw_inputs_by_checksum,
    get_extraction,
    get_extractions_for_raw_input,
    get_raw_input,
)
from traininglogs.db.insert import content_checksum, insert_extraction, insert_raw_input

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)

MARKDOWN = "# Training Log\n- Date: 2026-03-01\n**Name:** Leg Press\n1. 280 x 12 RPE 9.5\n"

EXTRACT = {
    "date": "2026-03-01",
    "focus": "Legs Hypertrophy",
    "exercises": [{"number": 1, "name": "Leg Press"}],
}


@pytest.fixture
def conn():
    connection = get_connection(TEST_DB_URL)
    apply_schema(connection)
    with connection.cursor() as cur:
        # raw_inputs cascades into extractions, so one truncate clears both.
        cur.execute("TRUNCATE raw_inputs CASCADE")
    connection.commit()
    yield connection
    connection.close()


class TestRawInputs:
    def test_stores_the_text_verbatim(self, conn) -> None:
        raw_id = insert_raw_input(conn, MARKDOWN, source_file="inputs/legs.md")
        row = get_raw_input(conn, raw_id)

        assert row is not None
        assert row["content"] == MARKDOWN, "the raw layer must not normalise what was written"
        assert row["source_kind"] == "markdown"
        assert row["source_file"] == "inputs/legs.md"
        assert row["captured_at"] is not None

    def test_checksum_is_of_the_content(self, conn) -> None:
        raw_id = insert_raw_input(conn, MARKDOWN)
        assert get_raw_input(conn, raw_id)["checksum"] == content_checksum(MARKDOWN)

    def test_source_file_is_optional(self, conn) -> None:
        """Speech and pasted text have no file to point at."""
        raw_id = insert_raw_input(conn, "did 5 sets of squats", source_kind="speech")
        assert get_raw_input(conn, raw_id)["source_file"] is None

    def test_an_unknown_source_kind_is_rejected(self, conn) -> None:
        with pytest.raises(psycopg2.errors.CheckViolation):
            insert_raw_input(conn, MARKDOWN, source_kind="telepathy")
        conn.rollback()

    def test_identical_text_is_stored_twice_not_collapsed(self, conn) -> None:
        """Repeating a session is a real thing a person does. Two captures must stay two
        captures; deduplication is the ingest path's decision, not storage's."""
        first = insert_raw_input(conn, MARKDOWN)
        second = insert_raw_input(conn, MARKDOWN)

        assert first != second
        found = find_raw_inputs_by_checksum(conn, content_checksum(MARKDOWN))
        assert [r["id"] for r in found] == [first, second]

    def test_missing_id_returns_none(self, conn) -> None:
        assert get_raw_input(conn, "does-not-exist") is None


class TestExtractions:
    def test_stores_the_extract_and_both_confidence_signals(self, conn) -> None:
        """`uncertain_fields` and `warnings` were computed and then discarded on the way to the
        normalized tables, leaving no record of how much to trust a row."""
        raw_id = insert_raw_input(conn, MARKDOWN)
        ext_id = insert_extraction(
            conn,
            raw_input_id=raw_id,
            model="claude-haiku-4-5-20251001",
            prompt_version="6458a555c922",
            extract=EXTRACT,
            uncertain_fields=["exercises.0.sets.1.rpe"],
            warnings=["RPE 9.0 appears in the text but not in any extracted set."],
        )
        row = get_extraction(conn, ext_id)

        assert row["extract"] == EXTRACT
        assert row["uncertain_fields"] == ["exercises.0.sets.1.rpe"]
        assert row["warnings"] == ["RPE 9.0 appears in the text but not in any extracted set."]
        assert row["model"] == "claude-haiku-4-5-20251001"
        assert row["prompt_version"] == "6458a555c922"

    def test_defaults_to_pending_and_unconfirmed(self, conn) -> None:
        raw_id = insert_raw_input(conn, MARKDOWN)
        ext_id = insert_extraction(conn, raw_id, "m", "v", EXTRACT)
        row = get_extraction(conn, ext_id)

        assert row["status"] == "pending"
        assert row["confirmed_at"] is None
        assert row["uncertain_fields"] == []
        assert row["warnings"] == []

    def test_an_unknown_status_is_rejected(self, conn) -> None:
        raw_id = insert_raw_input(conn, MARKDOWN)
        with pytest.raises(psycopg2.errors.CheckViolation):
            insert_extraction(conn, raw_id, "m", "v", EXTRACT, status="probably-fine")
        conn.rollback()

    def test_one_input_can_have_many_extractions(self, conn) -> None:
        """The whole point of separating the layers: re-reading the same text with a better
        model must not require re-writing it."""
        raw_id = insert_raw_input(conn, MARKDOWN)
        first = insert_extraction(conn, raw_id, "gpt-oss-120b", "v1", EXTRACT)
        second = insert_extraction(conn, raw_id, "claude-haiku-4-5", "v2", EXTRACT)

        found = get_extractions_for_raw_input(conn, raw_id)
        assert {r["id"] for r in found} == {first, second}
        assert [r["model"] for r in found][0] == "claude-haiku-4-5", "newest first"

    def test_an_extraction_cannot_orphan_itself_from_its_input(self, conn) -> None:
        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            insert_extraction(conn, "no-such-raw-input", "m", "v", EXTRACT)
        conn.rollback()

    def test_deleting_an_input_removes_its_extractions(self, conn) -> None:
        raw_id = insert_raw_input(conn, MARKDOWN)
        ext_id = insert_extraction(conn, raw_id, "m", "v", EXTRACT)

        with conn.cursor() as cur:
            cur.execute("DELETE FROM raw_inputs WHERE id = %s", (raw_id,))
        conn.commit()

        assert get_extraction(conn, ext_id) is None

    def test_missing_id_returns_none(self, conn) -> None:
        assert get_extraction(conn, "does-not-exist") is None


class TestPromptVersion:
    def test_it_tracks_the_prompts_it_describes(self) -> None:
        """Derived rather than declared, so it cannot go stale through forgetfulness — the one
        time a hand-bumped constant is forgotten is the one time the number was needed."""
        from traininglogs.agent import prompts

        before = prompts._prompt_version()
        original = prompts.WORKER_SYSTEM_PROMPT
        try:
            prompts.WORKER_SYSTEM_PROMPT = original + "\nOne more rule."
            assert prompts._prompt_version() != before
        finally:
            prompts.WORKER_SYSTEM_PROMPT = original
        assert prompts._prompt_version() == before
