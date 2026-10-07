"""What people wrote (`input_text`) and the AI's readings of it (`input_text_confirmation_cards`),
against the real test database: the constraints, defaults and cascades are most of what these
tables are.

A reading is derived from a note, so it must be possible to derive it again (a better model, a
fixed prompt) without asking the person to write anything twice. That's why a note can have many
cards, and why the text is stored whole.
"""
from __future__ import annotations

import psycopg2
import pytest

from signed_in import TEST_DB_URL, USER_A, clean_test_data
from traininglogs.db.db import apply_schema, get_connection
from traininglogs.db.fetch import get_card, get_cards_for_input, get_input
from traininglogs.db.ids import new_id
from traininglogs.db.insert import content_checksum, insert_card, insert_input

NOTE = "# Training Log\n- Date: 2026-03-01\n**Name:** Leg Press\n1. 280 x 12 RPE 9.5\n"
EXTRACT = {"date": "2026-03-01", "focus": "Legs Hypertrophy", "exercises": [{"number": 1, "name": "Leg Press"}]}


@pytest.fixture
def conn():
    connection = get_connection(TEST_DB_URL)
    apply_schema(connection)
    clean_test_data(connection)
    yield connection
    clean_test_data(connection)
    connection.close()


class TestInputText:
    def test_stores_the_text_verbatim(self, conn) -> None:
        input_id = insert_input(conn, USER_A, NOTE, source="inputs/legs.md")
        row = get_input(conn, USER_A, input_id)
        assert row["content"] == NOTE, "what was written is never normalised"
        assert (row["kind"], row["source"]) == ("text", "inputs/legs.md")
        assert row["created_at"] is not None

    def test_checksum_is_of_the_content(self, conn) -> None:
        input_id = insert_input(conn, USER_A, NOTE)
        with conn.cursor() as cur:
            cur.execute("SELECT checksum FROM input_text WHERE id = %s", (input_id,))
            assert cur.fetchone()[0] == content_checksum(NOTE)

    def test_an_unknown_kind_is_rejected(self, conn) -> None:
        with pytest.raises(psycopg2.errors.CheckViolation):
            insert_input(conn, USER_A, NOTE, kind="telepathy")
        conn.rollback()

    def test_identical_text_is_stored_twice_not_collapsed(self, conn) -> None:
        """Logging the same text twice is a real thing a person does; storage keeps both."""
        assert insert_input(conn, USER_A, NOTE) != insert_input(conn, USER_A, NOTE)

    def test_missing_id_returns_none(self, conn) -> None:
        assert get_input(conn, USER_A, new_id()) is None


class TestConfirmationCards:
    def test_stores_the_extract_and_both_confidence_signals(self, conn) -> None:
        input_id = insert_input(conn, USER_A, NOTE)
        card_id = insert_card(
            conn, USER_A, input_id, "claude-haiku-4-5-20251001", "6458a555c922", EXTRACT,
            uncertain_fields=["exercises.0.sets.1.rpe"],
            warnings=["RPE 9.0 appears in the text but not in any extracted set."],
        )
        row = get_card(conn, USER_A, card_id)
        assert row["extract"] == EXTRACT
        assert row["uncertain_fields"] == ["exercises.0.sets.1.rpe"]
        assert row["warnings"] == ["RPE 9.0 appears in the text but not in any extracted set."]
        assert (row["model"], row["prompt_version"]) == ("claude-haiku-4-5-20251001", "6458a555c922")

    def test_defaults_to_pending_and_unconfirmed(self, conn) -> None:
        row = get_card(conn, USER_A, insert_card(conn, USER_A, insert_input(conn, USER_A, NOTE), "m", "v", EXTRACT))
        assert (row["status"], row["confirmed_at"], row["uncertain_fields"], row["warnings"]) == ("pending", None, [], [])

    def test_an_unknown_status_is_rejected(self, conn) -> None:
        with pytest.raises(psycopg2.errors.CheckViolation):
            insert_card(conn, USER_A, insert_input(conn, USER_A, NOTE), "m", "v", EXTRACT, status="probably-fine")
        conn.rollback()

    def test_one_note_can_have_many_readings_newest_first(self, conn) -> None:
        input_id = insert_input(conn, USER_A, NOTE)
        first = insert_card(conn, USER_A, input_id, "gpt-oss-120b", "v1", EXTRACT)
        second = insert_card(conn, USER_A, input_id, "claude-haiku-4-5", "v2", EXTRACT)
        assert [r["id"] for r in get_cards_for_input(conn, USER_A, input_id)] == [second, first]

    def test_a_card_cannot_orphan_itself_from_its_note(self, conn) -> None:
        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            insert_card(conn, USER_A, new_id(), "m", "v", EXTRACT)
        conn.rollback()

    def test_deleting_a_note_removes_its_cards(self, conn) -> None:
        input_id = insert_input(conn, USER_A, NOTE)
        card_id = insert_card(conn, USER_A, input_id, "m", "v", EXTRACT)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM input_text WHERE id = %s", (input_id,))
        conn.commit()
        assert get_card(conn, USER_A, card_id) is None


class TestPromptVersion:
    def test_it_tracks_the_prompts_it_describes(self) -> None:
        """Derived rather than declared, so it can't go stale by being forgotten."""
        from traininglogs.agent import prompts

        before = prompts._prompt_version()
        original = prompts.WORKER_SYSTEM_PROMPT
        try:
            prompts.WORKER_SYSTEM_PROMPT = original + "\nOne more rule."
            assert prompts._prompt_version() != before
        finally:
            prompts.WORKER_SYSTEM_PROMPT = original
