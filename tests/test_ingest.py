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

        session_id = confirm(conn, "x1", make_extract(), md_path=md_path)

        with conn.cursor() as cur:
            cur.execute("SELECT extraction_id FROM sessions WHERE session_id = %s", (session_id,))
            assert cur.fetchone()[0] == "x1"

        stored = get_extraction(conn, "x1")
        assert stored["status"] == "confirmed"
        assert stored["confirmed_at"] is not None

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
