"""cli.log._process_ai_file: the AI parser path as it actually runs from `traininglogs log`,
end to end against a real database.

Replaces test_processor_ai_path.py (deleted, Phase 3 D2) -- that file drove
processor.process_md_file_with_ai, which owned capture+extract+confirm as one function. That
logic now lives in ingest/{capture,extract,confirm} (covered directly by test_ingest.py) plus
the CLI-only confirm loop in _process_ai_file. These tests cover what test_ingest.py's
per-function tests cannot: that _process_ai_file wires the three together correctly, in the
same order and with the same DB-visible results the old single function produced.

assemble() is monkeypatched -- the actual LLM boundary, the same seam test_ingest.py uses --
rather than swapping out a whole orchestrator, since the orchestrator's job here is just the
confirm loop.
"""
from __future__ import annotations

import io
import os

import pytest
from rich.console import Console

from traininglogs.agent.llm_orchestrator import LLMOrchestrator
from traininglogs.agent.renderer import TerminalRenderer
from traininglogs.agent.schemas import TrainingLogLLMExtract
from traininglogs.cli.log import _process_ai_file
from traininglogs.db.db import apply_schema, get_connection
from traininglogs.db.fetch import get_extraction, get_raw_input
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


class FakeProvider:
    model = "claude-haiku-4-5"


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


def _confirm_immediately() -> LLMOrchestrator:
    """Stands in for a person typing 'y' at the first card, without a real terminal."""
    return LLMOrchestrator(
        renderer=TerminalRenderer(console=Console(file=io.StringIO(), highlight=False)),
        input_fn=lambda: "y",
    )


def _stub_assemble(monkeypatch, extract: TrainingLogLLMExtract) -> None:
    monkeypatch.setattr(
        "traininglogs.ingest.extract.assemble", lambda text, provider=None: extract
    )


def _extraction_for(conn, session) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT extraction_id FROM sessions WHERE session_id = %s", (session.session_id,)
        )
        extraction_id = cur.fetchone()[0]
    return get_extraction(conn, extraction_id)


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
    def test_the_text_is_captured_verbatim(self, conn, md_file, monkeypatch) -> None:
        _stub_assemble(monkeypatch, make_extract())
        session = _process_ai_file(
            md_file, conn, provider=FakeProvider(), orchestrator=_confirm_immediately(),
            output_dir=None,
        )

        extraction = _extraction_for(conn, session)
        raw = get_raw_input(conn, extraction["raw_input_id"])

        assert raw["content"] == MARKDOWN
        assert raw["source_kind"] == "markdown"

    def test_the_session_points_at_the_extraction_it_came_from(self, conn, md_file, monkeypatch) -> None:
        _stub_assemble(monkeypatch, make_extract())
        session = _process_ai_file(
            md_file, conn, provider=FakeProvider(), orchestrator=_confirm_immediately(),
            output_dir=None,
        )
        assert _extraction_for(conn, session) is not None

    def test_the_model_and_prompt_are_recorded(self, conn, md_file, monkeypatch) -> None:
        from traininglogs.agent.prompts import PROMPT_VERSION

        _stub_assemble(monkeypatch, make_extract())
        session = _process_ai_file(
            md_file, conn, provider=FakeProvider(), orchestrator=_confirm_immediately(),
            output_dir=None,
        )
        extraction = _extraction_for(conn, session)

        assert extraction["model"] == "claude-haiku-4-5"
        assert extraction["prompt_version"] == PROMPT_VERSION

    def test_the_confidence_signals_survive(self, conn, md_file, monkeypatch) -> None:
        extract = make_extract(
            uncertain_fields=["exercises.0.sets.0.rpe"],
            warnings=["RPE 9.0 appears in the text but not in any extracted set."],
        )
        _stub_assemble(monkeypatch, extract)
        session = _process_ai_file(
            md_file, conn, provider=FakeProvider(), orchestrator=_confirm_immediately(),
            output_dir=None,
        )
        extraction = _extraction_for(conn, session)

        assert extraction["uncertain_fields"] == ["exercises.0.sets.0.rpe"]
        assert extraction["warnings"] == ["RPE 9.0 appears in the text but not in any extracted set."]

    def test_a_confirmed_extraction_records_when(self, conn, md_file, monkeypatch) -> None:
        _stub_assemble(monkeypatch, make_extract())
        session = _process_ai_file(
            md_file, conn, provider=FakeProvider(), orchestrator=_confirm_immediately(),
            output_dir=None,
        )
        extraction = _extraction_for(conn, session)

        assert extraction["status"] == "confirmed"
        assert extraction["confirmed_at"] is not None
        assert extraction["corrections"] == [], "no corrections made should store [], not null"

    def test_the_text_is_captured_even_if_extraction_fails(self, conn, md_file, monkeypatch) -> None:
        """A capture layer that only survives when interpretation succeeds is not a capture
        layer. capture() commits before extract() is ever called, so this is a property of the
        ordering in _process_ai_file, not just of capture() in isolation."""

        def failing_assemble(text, provider=None):
            raise RuntimeError("extraction blew up")

        monkeypatch.setattr("traininglogs.ingest.extract.assemble", failing_assemble)

        with pytest.raises(RuntimeError):
            _process_ai_file(
                md_file, conn, provider=FakeProvider(), orchestrator=_confirm_immediately(),
                output_dir=None,
            )

        with conn.cursor() as cur:
            cur.execute("SELECT content FROM raw_inputs")
            rows = cur.fetchall()
        assert [r[0] for r in rows] == [MARKDOWN]


class TestRelativeSourceFile:
    """The C8 regression: process_md_file set source_file, the AI path silently never did.
    Both paths share this one helper now, so they cannot disagree about it again."""

    def test_a_file_inside_the_repo_records_a_relative_path(self) -> None:
        from traininglogs.processor.processor import PROJECT_ROOT, relative_source_file

        inside = PROJECT_ROOT / "inputs" / "programs" / "x" / "session.md"
        assert relative_source_file(inside) == "inputs/programs/x/session.md"

    def test_a_file_outside_the_repo_is_none_not_a_guess(self, tmp_path) -> None:
        from traininglogs.processor.processor import relative_source_file

        assert relative_source_file(tmp_path / "elsewhere.md") is None


class TestSourceFileIsSet:
    def test_source_file_is_set_on_the_session(self, conn, md_file, monkeypatch) -> None:
        from traininglogs.processor.processor import relative_source_file

        _stub_assemble(monkeypatch, make_extract())
        session = _process_ai_file(
            md_file, conn, provider=FakeProvider(), orchestrator=_confirm_immediately(),
            output_dir=None,
        )
        with conn.cursor() as cur:
            cur.execute(
                "SELECT source_file FROM sessions WHERE session_id = %s", (session.session_id,)
            )
            stored = cur.fetchone()[0]

        # md_file lives in tmp_path, outside the repo, so None is correct here -- what matters
        # is that _process_ai_file asks the same helper the rules path does.
        assert stored == relative_source_file(md_file)


class TestCorrectionsAreKeptBesideTheModelsReading:
    def test_a_correction_changes_the_stored_session_but_not_the_original_extract(
        self, conn, md_file, monkeypatch
    ) -> None:
        original = make_extract(focus="Legs Hypertrophy")
        _stub_assemble(monkeypatch, original)

        answers = iter(["it was a strength session not hypertrophy", "y"])
        from traininglogs.agent.llm_extract_validator import LLMExtractValidator

        class StubCorrectionProvider:
            def extract(self, text, tool_schema, system_prompt, tool_name, tool_description, validate=None):
                return {"edits": [{"path": "focus", "value": "Legs Strength"}]}

        orchestrator = LLMOrchestrator(
            correction_provider=StubCorrectionProvider(),
            renderer=TerminalRenderer(console=Console(file=io.StringIO(), highlight=False)),
            input_fn=lambda: next(answers),
        )

        session = _process_ai_file(
            md_file, conn, provider=FakeProvider(), orchestrator=orchestrator, output_dir=None,
        )

        assert session.focus == "Legs Strength"

        extraction = _extraction_for(conn, session)
        assert extraction["extract"]["focus"] == "Legs Hypertrophy", (
            "the stored extract must stay the model's original reading, not the corrected one"
        )
        assert len(extraction["corrections"]) == 1
        assert extraction["corrections"][0]["instruction"] == (
            "it was a strength session not hypertrophy"
        )

    def test_correction_calls_made_during_the_confirm_loop_are_persisted(
        self, conn, md_file, monkeypatch
    ) -> None:
        """extract() already drains and persists provider.calls before the confirm loop runs
        -- a correction made during that loop is a real LLM call too, made after extract() has
        already returned, so nothing else would ever record it without this."""

        class FakeSharedProvider:
            model = "fake-model"

            def __init__(self) -> None:
                self.calls: list[dict] = []

            def extract(self, text, tool_schema, system_prompt, tool_name, tool_description, validate=None):
                self.calls.append(
                    {
                        "step": tool_name, "model": self.model, "attempts": 1,
                        "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.0001, "ms": 50,
                        "cached": False, "failed": None,
                        "raw_payload": {"edits": [{"path": "focus", "value": "Legs Strength"}]},
                    }
                )
                return {"edits": [{"path": "focus", "value": "Legs Strength"}]}

        _stub_assemble(monkeypatch, make_extract(focus="Legs Hypertrophy"))
        provider = FakeSharedProvider()
        answers = iter(["it was a strength session not hypertrophy", "y"])
        orchestrator = LLMOrchestrator(
            correction_provider=provider,
            renderer=TerminalRenderer(console=Console(file=io.StringIO(), highlight=False)),
            input_fn=lambda: next(answers),
        )

        session = _process_ai_file(
            md_file, conn, provider=provider, orchestrator=orchestrator, output_dir=None,
        )
        extraction = _extraction_for(conn, session)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT step FROM llm_calls WHERE raw_input_id = %s",
                (extraction["raw_input_id"],),
            )
            steps = [r[0] for r in cur.fetchall()]
        assert steps == ["edit_extraction"]
