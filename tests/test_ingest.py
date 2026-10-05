"""The ingest/ module: three single-job functions, each reading its input from the database
and saving its own output before returning (roadmap Phase 3, D1).

capture(, user_id=USER_A) and confirm() are already covered end-to-end via test_processor_ai_path.py's use of
process_md_file_with_ai. These tests exercise the ingest/ functions directly, including the
behavior process_md_file_with_ai does not yet exercise: extract()'s idempotency (D3).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from traininglogs.agent.schemas import TrainingLogLLMExtract
from traininglogs.db.db import apply_schema, get_connection
from traininglogs.db.fetch import get_card, get_input, get_session
from traininglogs.db.ids import new_id
from traininglogs.db.insert import insert_card, insert_input
from traininglogs.ingest.confirm import AlreadySaved, confirm, dedup_key
from traininglogs.ingest.extract import extract
from traininglogs.models.models import Exercise, RepCount, WorkingSet

from signed_in import USER_A, clean_test_data

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)

MARKDOWN = """# Training Log
- Date: 2026-03-01
- Focus: Legs Hypertrophy

## Exercise 1
**Name:** Leg Press
### Working Sets
1. 280 x 12 RPE 9.5
"""


def make_extract(**overrides) -> TrainingLogLLMExtract:
    base = dict(
        date="2026-03-01",
        focus="Legs Hypertrophy",
        exercises=[
            Exercise(
                number=1,
                name="Leg Press",
                sets=[WorkingSet(number=1, weight_kg=280.0, rep_count=RepCount(full=12, partial=0), rpe=9.5)],
            )
        ],
    )
    base.update(overrides)
    return TrainingLogLLMExtract(**base)


@pytest.fixture
def conn():
    connection = get_connection(TEST_DB_URL)
    apply_schema(connection)
    clean_test_data(connection)
    yield connection
    clean_test_data(connection)
    connection.close()


class FakeProvider:
    model = "fake-model"


def _note(conn, text: str = MARKDOWN) -> str:
    return insert_input(conn, USER_A, text)


class TestExtract:
    def test_calls_assemble_and_saves_a_pending_card(self, conn, monkeypatch) -> None:
        seen = []

        def fake_assemble(text, provider=None):
            seen.append((text, provider))
            return make_extract()

        monkeypatch.setattr("traininglogs.ingest.extract.assemble", fake_assemble)
        input_id = _note(conn)
        card_id = extract(conn, USER_A, input_id, provider=FakeProvider())

        assert [text for text, _ in seen] == [MARKDOWN]
        stored = get_card(conn, USER_A, card_id)
        assert (stored["input_id"], stored["status"], stored["confirmed_at"], stored["model"]) == (
            input_id, "pending", None, "fake-model")

    def test_is_idempotent_for_a_pending_card(self, conn, monkeypatch) -> None:
        calls = {"n": 0}

        def fake_assemble(text, provider=None):
            calls["n"] += 1
            return make_extract()

        monkeypatch.setattr("traininglogs.ingest.extract.assemble", fake_assemble)
        input_id = _note(conn)
        assert extract(conn, USER_A, input_id, provider=FakeProvider()) == extract(conn, USER_A, input_id, provider=FakeProvider())
        assert calls["n"] == 1, "reading a note again must not pay for a second call"

    def test_a_rejected_card_does_not_block_a_new_reading(self, conn, monkeypatch) -> None:
        monkeypatch.setattr("traininglogs.ingest.extract.assemble", lambda text, provider=None: make_extract())
        input_id = _note(conn)
        first = extract(conn, USER_A, input_id, provider=FakeProvider())
        with conn.cursor() as cur:
            cur.execute("UPDATE input_text_confirmation_cards SET status = 'rejected' WHERE id = %s", (first,))
        conn.commit()
        assert extract(conn, USER_A, input_id, provider=FakeProvider()) != first

    def test_raises_for_an_unknown_note(self, conn) -> None:
        with pytest.raises(ValueError):
            extract(conn, USER_A, new_id())

    def test_a_date_the_ai_flagged_unsure_is_filled_from_when_the_note_was_saved(self, conn, monkeypatch) -> None:
        """The AI can't know the date if the text doesn't say; the day the note was saved fills the
        gap, still flagged, since "saved today" isn't "trained today"."""
        monkeypatch.setattr(
            "traininglogs.ingest.extract.assemble",
            lambda text, provider=None: make_extract(date="2000-01-01", uncertain_fields=["date"]),
        )
        input_id = _note(conn)
        stored = get_card(conn, USER_A, extract(conn, USER_A, input_id, provider=FakeProvider()))
        assert stored["extract"]["date"] == get_input(conn, USER_A, input_id)["created_at"].strftime("%Y-%m-%d")
        assert "date" in stored["uncertain_fields"]

    def test_a_date_the_ai_is_sure_of_is_left_alone(self, conn, monkeypatch) -> None:
        monkeypatch.setattr("traininglogs.ingest.extract.assemble", lambda text, provider=None: make_extract(date="2026-03-01"))
        stored = get_card(conn, USER_A, extract(conn, USER_A, _note(conn), provider=FakeProvider()))
        assert stored["extract"]["date"] == "2026-03-01"
        assert "date" not in stored["uncertain_fields"]


class FakeProviderWithCalls:
    """A provider whose `.calls` is already filled, as AnthropicProvider is after a reading."""

    model = "fake-model"

    def __init__(self, calls: list[dict]) -> None:
        self.calls = calls


def _call_record(step: str, **overrides) -> dict:
    return dict(step=step, model="fake-model", attempts=1, input_tokens=100, output_tokens=50,
                cost_usd=0.0007, ms=250, cached=False, failed=None, raw_payload={"ok": True}) | overrides


def _logged(conn, input_id: str, columns: str = "step") -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(f"SELECT {columns} FROM ai_call_logs WHERE input_id = %s ORDER BY id", (input_id,))
        return cur.fetchall()


class TestAiCallsAreLogged:
    def test_each_call_becomes_a_row_with_its_tokens_and_cost(self, conn, monkeypatch) -> None:
        monkeypatch.setattr("traininglogs.ingest.extract.assemble", lambda text, provider=None: make_extract())
        input_id = _note(conn)
        extract(conn, USER_A, input_id, provider=FakeProviderWithCalls(
            [_call_record("segment"), _call_record("worker", input_tokens=1234, output_tokens=567, cost_usd=0.004532)]))
        rows = _logged(conn, input_id, "step, input_tokens, output_tokens, cost_usd")
        assert [r[0] for r in rows] == ["segment", "worker"]
        assert (rows[1][1], rows[1][2], float(rows[1][3])) == (1234, 567, pytest.approx(0.004532))

    def test_calls_are_logged_even_if_the_reading_fails(self, conn, monkeypatch) -> None:
        """A run that fails partway still paid for its calls."""
        def failing_assemble(text, provider=None):
            raise RuntimeError("worker blew up")

        monkeypatch.setattr("traininglogs.ingest.extract.assemble", failing_assemble)
        input_id = _note(conn)
        with pytest.raises(RuntimeError):
            extract(conn, USER_A, input_id, provider=FakeProviderWithCalls([_call_record("segment"), _call_record("shell")]))
        assert len(_logged(conn, input_id)) == 2

    def test_a_provider_with_no_calls_logs_nothing(self, conn, monkeypatch) -> None:
        monkeypatch.setattr("traininglogs.ingest.extract.assemble", lambda text, provider=None: make_extract())
        input_id = _note(conn)
        assert extract(conn, USER_A, input_id, provider=FakeProvider())
        assert _logged(conn, input_id) == []

    def test_a_failed_call_is_kept_with_its_error_and_raw_payload(self, conn, monkeypatch) -> None:
        monkeypatch.setattr("traininglogs.ingest.extract.assemble", lambda text, provider=None: make_extract())
        input_id = _note(conn)
        extract(conn, USER_A, input_id, provider=FakeProviderWithCalls(
            [_call_record("worker", failed="LLMParserError: bad payload", raw_payload={"bad": 1})]))
        assert _logged(conn, input_id, "failed, raw_payload") == [("LLMParserError: bad payload", {"bad": 1})]


def _card(conn, text: str = MARKDOWN) -> str:
    return insert_card(conn, USER_A, _note(conn, text), "m", "v1", {})


class TestConfirm:
    def test_saves_the_session_and_marks_the_card_confirmed(self, conn) -> None:
        card_id = _card(conn)
        session_id = confirm(conn, USER_A, card_id, make_extract())
        with conn.cursor() as cur:
            cur.execute("SELECT confirmation_card_id::text FROM workout_sessions WHERE id = %s", (session_id,))
            assert cur.fetchone()[0] == card_id
        stored = get_card(conn, USER_A, card_id)
        assert stored["status"] == "confirmed" and stored["confirmed_at"] is not None
        assert get_session(conn, USER_A, session_id)["focus"] == "Legs Hypertrophy"

    def test_records_corrections_on_the_card(self, conn) -> None:
        card_id = _card(conn)
        corrections = [{"at": "2026-08-09T10:00:00+00:00", "instruction": "fix it", "edits": []}]
        confirm(conn, USER_A, card_id, make_extract(), corrections=corrections)
        assert get_card(conn, USER_A, card_id)["corrections"] == corrections

    def test_raises_for_an_unknown_card(self, conn) -> None:
        with pytest.raises(ValueError):
            confirm(conn, USER_A, new_id(), make_extract())

    def test_the_dedup_key_comes_from_the_notes_text_and_date(self, conn) -> None:
        session_id = confirm(conn, USER_A, _card(conn), make_extract())
        with conn.cursor() as cur:
            cur.execute("SELECT dedup_key FROM workout_sessions WHERE id = %s", (session_id,))
            assert cur.fetchone()[0] == dedup_key(MARKDOWN, "2026-03-01")

    def test_the_same_note_confirmed_twice_is_refused(self, conn) -> None:
        confirm(conn, USER_A, _card(conn), make_extract())
        with pytest.raises(AlreadySaved):
            confirm(conn, USER_A, _card(conn), make_extract())

    def test_whitespace_only_differences_are_the_same_note(self, conn) -> None:
        confirm(conn, USER_A, _card(conn), make_extract())
        with pytest.raises(AlreadySaved):
            confirm(conn, USER_A, _card(conn, MARKDOWN + "\n\n"), make_extract())
