"""The ingest/ module: three single-job functions, each reading its input from the database
and saving its own output before returning (roadmap Phase 3, D1).

capture() and confirm() are already covered end-to-end via test_processor_ai_path.py's use of
process_md_file_with_ai. These tests exercise the ingest/ functions directly, including the
behavior process_md_file_with_ai does not yet exercise: extract()'s idempotency (D3).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from traininglogs.agent.schemas import TrainingLogLLMExtract
from traininglogs.db.db import apply_schema, get_connection
from traininglogs.db.fetch import get_extraction, get_raw_input
from traininglogs.ingest.capture import capture
from traininglogs.ingest.confirm import confirm
from traininglogs.ingest.extract import extract
from traininglogs.models.models import Exercise, RepCount, WorkingSet

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
    with connection.cursor() as cur:
        cur.execute("TRUNCATE sessions CASCADE")
        cur.execute("TRUNCATE raw_inputs CASCADE")
    connection.commit()
    yield connection
    connection.close()


class FakeProvider:
    model = "fake-model"


class TestCapture:
    def test_stores_the_text_verbatim_and_returns_its_id(self, conn) -> None:
        raw_input_id = capture(conn, MARKDOWN, source_kind="markdown", source_file="a.md")

        raw = get_raw_input(conn, raw_input_id)
        assert raw["content"] == MARKDOWN
        assert raw["source_kind"] == "markdown"
        assert raw["source_file"] == "a.md"


class TestExtract:
    def test_calls_assemble_and_saves_a_pending_extraction(self, conn, monkeypatch) -> None:
        seen = []

        def fake_assemble(text, provider=None):
            seen.append((text, provider))
            return make_extract()

        monkeypatch.setattr("traininglogs.ingest.extract.assemble", fake_assemble)

        raw_input_id = capture(conn, MARKDOWN)
        extraction_id = extract(conn, raw_input_id, provider=FakeProvider())

        assert seen == [(MARKDOWN, seen[0][1])]
        assert seen[0][1] is not None

        stored = get_extraction(conn, extraction_id)
        assert stored["raw_input_id"] == raw_input_id
        assert stored["status"] == "pending"
        assert stored["confirmed_at"] is None
        assert stored["model"] == "fake-model"

    def test_is_idempotent_for_a_pending_extraction(self, conn, monkeypatch) -> None:
        calls = {"n": 0}

        def fake_assemble(text, provider=None):
            calls["n"] += 1
            return make_extract()

        monkeypatch.setattr("traininglogs.ingest.extract.assemble", fake_assemble)

        raw_input_id = capture(conn, MARKDOWN)
        first_id = extract(conn, raw_input_id, provider=FakeProvider())
        second_id = extract(conn, raw_input_id, provider=FakeProvider())

        assert first_id == second_id
        assert calls["n"] == 1, "re-running extract on an already-extracted input must not pay for a second call"

    def test_a_rejected_extraction_does_not_block_a_new_attempt(self, conn, monkeypatch) -> None:
        calls = {"n": 0}

        def fake_assemble(text, provider=None):
            calls["n"] += 1
            return make_extract()

        monkeypatch.setattr("traininglogs.ingest.extract.assemble", fake_assemble)

        raw_input_id = capture(conn, MARKDOWN)
        first_id = extract(conn, raw_input_id, provider=FakeProvider())
        with conn.cursor() as cur:
            cur.execute("UPDATE extractions SET status = 'rejected' WHERE id = %s", (first_id,))
        conn.commit()

        second_id = extract(conn, raw_input_id, provider=FakeProvider())

        assert second_id != first_id
        assert calls["n"] == 2

    def test_raises_for_an_unknown_raw_input(self, conn) -> None:
        with pytest.raises(ValueError):
            extract(conn, "does-not-exist")


class FakeProviderWithCalls:
    """A provider whose `.calls` is already populated, standing in for what
    AnthropicProvider looks like after assemble() has driven it through a few steps."""

    model = "fake-model"

    def __init__(self, calls: list[dict]) -> None:
        self.calls = calls


def _call_record(step: str, **overrides) -> dict:
    base = dict(
        step=step, model="fake-model", attempts=1, input_tokens=100, output_tokens=50,
        cost_usd=0.0007, ms=250, cached=False, failed=None, raw_payload={"ok": True},
    )
    base.update(overrides)
    return base


class TestLLMCallsArePersisted:
    """D4: cost becomes a SQL query. D5: every row is findable by raw_input_id."""

    def test_each_call_the_provider_made_becomes_a_row(self, conn, monkeypatch) -> None:
        monkeypatch.setattr(
            "traininglogs.ingest.extract.assemble", lambda text, provider=None: make_extract()
        )
        provider = FakeProviderWithCalls(
            [_call_record("segment"), _call_record("shell"), _call_record("worker")]
        )
        raw_input_id = capture(conn, MARKDOWN)

        extract(conn, raw_input_id, provider=provider)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT step FROM llm_calls WHERE raw_input_id = %s ORDER BY id", (raw_input_id,)
            )
            steps = [r[0] for r in cur.fetchall()]
        assert steps == ["segment", "shell", "worker"]

    def test_tokens_and_cost_are_stored(self, conn, monkeypatch) -> None:
        monkeypatch.setattr(
            "traininglogs.ingest.extract.assemble", lambda text, provider=None: make_extract()
        )
        provider = FakeProviderWithCalls(
            [_call_record("worker", input_tokens=1234, output_tokens=567, cost_usd=0.004532)]
        )
        raw_input_id = capture(conn, MARKDOWN)

        extract(conn, raw_input_id, provider=provider)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT input_tokens, output_tokens, cost_usd FROM llm_calls "
                "WHERE raw_input_id = %s",
                (raw_input_id,),
            )
            row = cur.fetchone()
        assert row[0] == 1234
        assert row[1] == 567
        assert float(row[2]) == pytest.approx(0.004532)

    def test_calls_are_persisted_even_if_assemble_raises(self, conn, monkeypatch) -> None:
        """A run that fails partway through still spent money on the calls it made -- that
        cost must not vanish with the exception (roadmap D4's whole point)."""
        provider = FakeProviderWithCalls([_call_record("segment"), _call_record("shell")])

        def failing_assemble(text, provider=None):
            raise RuntimeError("worker blew up")

        monkeypatch.setattr("traininglogs.ingest.extract.assemble", failing_assemble)
        raw_input_id = capture(conn, MARKDOWN)

        with pytest.raises(RuntimeError):
            extract(conn, raw_input_id, provider=provider)

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM llm_calls WHERE raw_input_id = %s", (raw_input_id,))
            assert cur.fetchone()[0] == 2

    def test_a_provider_with_no_calls_attribute_does_not_break_extract(self, conn, monkeypatch) -> None:
        """Most test doubles (FakeProvider above, StubProvider elsewhere) have no `.calls` --
        extract() must not require it."""
        monkeypatch.setattr(
            "traininglogs.ingest.extract.assemble", lambda text, provider=None: make_extract()
        )
        raw_input_id = capture(conn, MARKDOWN)

        extraction_id = extract(conn, raw_input_id, provider=FakeProvider())

        assert extraction_id is not None
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM llm_calls WHERE raw_input_id = %s", (raw_input_id,))
            assert cur.fetchone()[0] == 0

    def test_a_failed_call_is_stored_with_its_error_and_raw_payload(self, conn, monkeypatch) -> None:
        monkeypatch.setattr(
            "traininglogs.ingest.extract.assemble", lambda text, provider=None: make_extract()
        )
        provider = FakeProviderWithCalls(
            [_call_record("worker", failed="LLMParserError: bad payload", raw_payload={"bad": 1})]
        )
        raw_input_id = capture(conn, MARKDOWN)

        extract(conn, raw_input_id, provider=provider)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT failed, raw_payload FROM llm_calls WHERE raw_input_id = %s", (raw_input_id,)
            )
            failed, raw_payload = cur.fetchone()
        assert failed == "LLMParserError: bad payload"
        assert raw_payload == {"bad": 1}


class TestConfirm:
    def test_writes_the_session_and_marks_the_extraction_confirmed(self, conn, tmp_path) -> None:
        raw_input_id = capture(conn, MARKDOWN)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO extractions (id, raw_input_id, model, prompt_version, extract) "
                "VALUES ('x1', %s, 'm', 'v1', '{}')",
                (raw_input_id,),
            )
        conn.commit()

        md_path = tmp_path / "leg_press.md"
        md_path.write_text(MARKDOWN)

        session = confirm(conn, "x1", make_extract(), md_path=md_path)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT extraction_id FROM sessions WHERE session_id = %s", (session.session_id,)
            )
            assert cur.fetchone()[0] == "x1"

        stored = get_extraction(conn, "x1")
        assert stored["status"] == "confirmed"
        assert stored["confirmed_at"] is not None

    def test_returns_the_full_session_not_just_its_id(self, conn, tmp_path) -> None:
        """The caller (cli/log.py) needs the whole object to re-insert into the local DB
        mirror -- returning a bare id would force it to re-fetch what it already just built."""
        from traininglogs.models.models import TrainingSession

        raw_input_id = capture(conn, MARKDOWN)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO extractions (id, raw_input_id, model, prompt_version, extract) "
                "VALUES ('x3', %s, 'm', 'v1', '{}')",
                (raw_input_id,),
            )
        conn.commit()

        md_path = tmp_path / "leg_press.md"
        md_path.write_text(MARKDOWN)

        session = confirm(conn, "x3", make_extract(), md_path=md_path, source_file="a.md")

        assert isinstance(session, TrainingSession)
        assert session.focus == "Legs Hypertrophy"
        with conn.cursor() as cur:
            cur.execute(
                "SELECT source_file FROM sessions WHERE session_id = %s", (session.session_id,)
            )
            assert cur.fetchone()[0] == "a.md"

    def test_records_corrections_on_the_extraction(self, conn, tmp_path) -> None:
        raw_input_id = capture(conn, MARKDOWN)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO extractions (id, raw_input_id, model, prompt_version, extract) "
                "VALUES ('x2', %s, 'm', 'v1', '{}')",
                (raw_input_id,),
            )
        conn.commit()

        md_path = tmp_path / "leg_press.md"
        md_path.write_text(MARKDOWN)
        corrections = [{"at": "2026-08-09T10:00:00+00:00", "instruction": "fix it", "edits": []}]

        confirm(conn, "x2", make_extract(), md_path=md_path, corrections=corrections)

        assert get_extraction(conn, "x2")["corrections"] == corrections

    def test_raises_for_an_unknown_extraction(self, conn, tmp_path) -> None:
        md_path = tmp_path / "leg_press.md"
        md_path.write_text(MARKDOWN)
        with pytest.raises(ValueError):
            confirm(conn, "does-not-exist", make_extract(), md_path=md_path)
