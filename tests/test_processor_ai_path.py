"""The AI parser path, end to end against a real database, with the model faked out.

This file exists because of a specific bug. `source_file` was set by the rules path and silently
never set by the AI path, so every AI-parsed session in the database has no link to the text it
came from. It survived because the code lived nested inside the CLI where nothing could reach it
— so the fix is not only the parameter, it is that this path is now callable and tested.
"""
from __future__ import annotations

import os

import pytest

from traininglogs.agent.schemas import TrainingLogLLMExtract
from traininglogs.db.db import apply_schema, get_connection
from traininglogs.db.fetch import get_extraction, get_raw_input
from traininglogs.models.models import Exercise, RepCount, WorkingSet
from traininglogs.processor.processor import (
    process_md_file,
    process_md_file_with_ai,
    relative_source_file,
)

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


class FakeOrchestrator:
    """Stands in for the confirmation loop. Returns an already-confirmed extract."""

    def __init__(self, extract: TrainingLogLLMExtract) -> None:
        self._extract = extract
        self.texts_seen: list[str] = []

    def run(self, text: str) -> TrainingLogLLMExtract:
        self.texts_seen.append(text)
        return self._extract


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


@pytest.fixture
def md_file(tmp_path):
    path = tmp_path / "legs_hypertrophy.md"
    path.write_text(MARKDOWN, encoding="utf-8")
    return path


class TestTheThreeLayersAreWritten:
    def test_the_text_is_captured_verbatim(self, conn, md_file) -> None:
        session = process_md_file_with_ai(
            md_file, conn, orchestrator=FakeOrchestrator(make_extract()),
            model="claude-haiku-4-5", output_dir=None,
        )

        with conn.cursor() as cur:
            cur.execute("SELECT extraction_id FROM sessions WHERE session_id = %s",
                        (session.session_id,))
            extraction_id = cur.fetchone()[0]
        extraction = get_extraction(conn, extraction_id)
        raw = get_raw_input(conn, extraction["raw_input_id"])

        assert raw["content"] == MARKDOWN
        assert raw["source_kind"] == "markdown"

    def test_the_session_points_at_the_extraction_it_came_from(self, conn, md_file) -> None:
        session = process_md_file_with_ai(
            md_file, conn, orchestrator=FakeOrchestrator(make_extract()),
            model="claude-haiku-4-5", output_dir=None,
        )

        with conn.cursor() as cur:
            cur.execute("SELECT extraction_id FROM sessions WHERE session_id = %s",
                        (session.session_id,))
            extraction_id = cur.fetchone()[0]

        assert extraction_id is not None, "a session with no extraction cannot be traced back"
        assert get_extraction(conn, extraction_id) is not None

    def test_the_model_and_prompt_are_recorded(self, conn, md_file) -> None:
        """Without both, a change in accuracy months from now is unattributable."""
        from traininglogs.agent.prompts import PROMPT_VERSION

        session = process_md_file_with_ai(
            md_file, conn, orchestrator=FakeOrchestrator(make_extract()),
            model="claude-haiku-4-5", output_dir=None,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT extraction_id FROM sessions WHERE session_id = %s",
                        (session.session_id,))
            extraction = get_extraction(conn, cur.fetchone()[0])

        assert extraction["model"] == "claude-haiku-4-5"
        assert extraction["prompt_version"] == PROMPT_VERSION

    def test_the_confidence_signals_survive(self, conn, md_file) -> None:
        """`uncertain_fields` and `warnings` were computed and then dropped on the way to the
        normalized tables, so nothing recorded how much to trust a row."""
        extract = make_extract(
            uncertain_fields=["exercises.0.sets.0.rpe"],
            warnings=["RPE 9.0 appears in the text but not in any extracted set."],
        )
        session = process_md_file_with_ai(
            md_file, conn, orchestrator=FakeOrchestrator(extract),
            model="m", output_dir=None,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT extraction_id FROM sessions WHERE session_id = %s",
                        (session.session_id,))
            stored = get_extraction(conn, cur.fetchone()[0])

        assert stored["uncertain_fields"] == ["exercises.0.sets.0.rpe"]
        assert stored["warnings"] == ["RPE 9.0 appears in the text but not in any extracted set."]

    def test_a_confirmed_extraction_records_when(self, conn, md_file) -> None:
        """status and confirmed_at are one decision, not two that must be kept in agreement."""
        session = process_md_file_with_ai(
            md_file, conn, orchestrator=FakeOrchestrator(make_extract()),
            model="m", output_dir=None,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT extraction_id FROM sessions WHERE session_id = %s",
                        (session.session_id,))
            stored = get_extraction(conn, cur.fetchone()[0])

        assert stored["status"] == "confirmed"
        assert stored["confirmed_at"] is not None

    def test_the_text_is_captured_before_the_model_is_asked_anything(self, conn, md_file) -> None:
        """A capture layer that only survives when interpretation succeeds is not a capture
        layer. If the model fails, what the person wrote must still be there."""

        class FailingOrchestrator:
            def run(self, text: str):
                raise RuntimeError("extraction blew up")

        with pytest.raises(RuntimeError):
            process_md_file_with_ai(md_file, conn, orchestrator=FailingOrchestrator(),
                                    model="m", output_dir=None)

        with conn.cursor() as cur:
            cur.execute("SELECT content FROM raw_inputs")
            rows = cur.fetchall()
        assert [r[0] for r in rows] == [MARKDOWN]


class TestSourceFileIsSetOnBothPaths:
    """The C8 regression. One path set it, the other never did, and nothing noticed."""

    def test_ai_path_sets_source_file(self, conn, md_file) -> None:
        session = process_md_file_with_ai(
            md_file, conn, orchestrator=FakeOrchestrator(make_extract()),
            model="m", output_dir=None,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT source_file FROM sessions WHERE session_id = %s",
                        (session.session_id,))
            stored = cur.fetchone()[0]

        # tmp_path lives outside the repo, so the helper correctly reports None rather than
        # inventing a path. What matters is that the AI path asks the same question the rules
        # path does, through the same helper.
        assert stored == relative_source_file(md_file)

    def test_a_file_inside_the_repo_records_a_relative_path(self) -> None:
        from traininglogs.processor.processor import PROJECT_ROOT

        inside = PROJECT_ROOT / "inputs" / "programs" / "x" / "session.md"
        assert relative_source_file(inside) == "inputs/programs/x/session.md"

    def test_a_file_outside_the_repo_is_none_not_a_guess(self, tmp_path) -> None:
        assert relative_source_file(tmp_path / "elsewhere.md") is None


class TestPlaceholdersRemainQueryable:
    def test_a_failed_exercise_is_findable_by_warning_not_by_prose(self, conn, md_file) -> None:
        """A worker that fails becomes a placeholder exercise. That is a deliberate, confirmed
        choice by the person at the card — but before this step, finding such sessions meant a
        LIKE against a notes column. The warning on the extraction makes it a real query."""
        extract = make_extract(
            warnings=["Exercise 1 (Leg Press) failed to extract: LLM extraction failed"]
        )
        process_md_file_with_ai(
            md_file, conn, orchestrator=FakeOrchestrator(extract), model="m", output_dir=None,
        )

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM extractions WHERE warnings <> '{}'")
            assert cur.fetchone()[0] == 1
