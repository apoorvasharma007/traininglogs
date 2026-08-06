"""Integration tests for assemble() — the split-extraction glue: segment() -> extract_shell()
-> one extract_exercise() worker call per position -> TrainingLogLLMExtract. Fake providers
only, no real LLM calls.

The model owns the numeric spine, so every scripted worker response here supplies its own
sets/warmup_sets (see _exercise_raw). A deterministic pre-parse used to fill those in from the
real chunk text (parse_exercise_block, removed 2026-08-03 — it fired on 0 of 10 exercises in
real input); these tests now cover what the assembler does with a worker's answer, not where
the numbers came from."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from traininglogs.agent.extraction import (
    SEGMENT_TOOL_NAME,
    SHELL_TOOL_NAME,
    WORKER_TOOL_NAME,
    assemble,
)
from traininglogs.agent.schemas import LLMParserError

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "valid"


class ScriptedProvider:
    """Dispatches by tool_name (splitter / shell / worker). Worker calls are dispatched by call
    order, not by the position number embedded in the prompt text: assemble() passes 1 (the
    chunk-local position) for every successfully-isolated chunk, not the splitter's global
    split_position — so every chunked worker call's prompt says "exercise number 1" no matter
    which real exercise it's for, and parsing that number can't tell calls apart. assemble()
    calls workers in split order, one per entry, so the Nth worker call always corresponds to
    the Nth entry in split_raw["exercises"] — that ordering, not the prompt text, is what
    identifies each call's split_position here."""

    def __init__(
        self,
        split_raw: dict[str, Any],
        shell_raw: dict[str, Any],
        exercise_raw_by_position: dict[int, dict[str, Any]],
    ) -> None:
        self._split_raw = split_raw
        self._shell_raw = shell_raw
        self._exercise_raw_by_position = exercise_raw_by_position
        self._worker_call_count = 0
        self.worker_calls: list[int] = []
        self.worker_texts: dict[int, str] = {}
        self.worker_tool_names: list[str] = []

    def extract(
        self, text: str, tool_schema: dict, system_prompt: str, tool_name: str,
        tool_description: str, validate=None
    ) -> dict:
        if tool_name == SEGMENT_TOOL_NAME:
            return self._split_raw
        if tool_name == SHELL_TOOL_NAME:
            return self._shell_raw
        if tool_name == WORKER_TOOL_NAME:
            # This is the Nth worker call overall -> it's for the Nth exercise in the split,
            # by call order (see class docstring), not by anything in the prompt text.
            split_position = self._split_raw["exercises"][self._worker_call_count]["position"]
            self._worker_call_count += 1
            self.worker_calls.append(split_position)
            self.worker_texts[split_position] = text
            self.worker_tool_names.append(tool_name)
            raw = self._exercise_raw_by_position.get(split_position)
            if raw is None:
                raise LLMParserError(f"no scripted response for position {split_position}")
            return raw
        raise AssertionError(f"unexpected tool_name: {tool_name}")


def _exercise_raw(number: int, name: str, **overrides: Any) -> dict[str, Any]:
    """ExerciseExtract fixture — one scripted worker response. Override `sets` when a test
    asserts specific numbers; the default single 50kg x 8 set is enough for tests that only
    care that *an* exercise came through."""
    base: dict[str, Any] = {
        "number": number,
        "name": name,
        "sets": [
            {"number": 1, "source_line": "1. 50kg x 8", "weight_kg": 50.0, "reps": "8"}
        ],
        "uncertain_fields": [],
    }
    base.update(overrides)
    return base


SAMPLE_TWO_EXERCISE_TEXT = """Bench Press
Sets:
1. 80kg x 8

Overhead Press
Sets:
1. 40kg x 8
"""


class TestAssembleIntegration:
    def test_glues_shell_and_exercises_in_order(self) -> None:
        provider = ScriptedProvider(
            split_raw={
                "exercises": [
                    {"position": 1, "name": "Bench Press", "anchor": "Bench Press"},
                    {"position": 2, "name": "Overhead Press", "anchor": "Overhead Press"},
                ]
            },
            shell_raw={"date": "2026-05-12", "focus": "Upper", "session_duration_minutes": 60},
            exercise_raw_by_position={
                1: _exercise_raw(
                    1,
                    "Bench Press",
                    sets=[{"number": 1, "source_line": "1. 80kg x 8", "weight_kg": 80.0, "reps": "8"}],
                ),
                2: _exercise_raw(
                    2,
                    "Overhead Press",
                    sets=[{"number": 1, "source_line": "1. 40kg x 8", "weight_kg": 40.0, "reps": "8"}],
                ),
            },
        )

        extract = assemble(SAMPLE_TWO_EXERCISE_TEXT, provider=provider)

        assert extract.date == "2026-05-12"
        assert extract.focus == "Upper"
        assert [e.name for e in extract.exercises] == ["Bench Press", "Overhead Press"]
        assert extract.exercises[0].sets[0].weight_kg == 80.0
        assert extract.exercises[1].sets[0].weight_kg == 40.0
        assert extract.warnings == []
        assert provider.worker_calls == [1, 2]
        assert provider.worker_tool_names == [WORKER_TOOL_NAME, WORKER_TOOL_NAME]

    def test_worker_uncertain_fields_get_prefixed_with_exercise_index(self) -> None:
        provider = ScriptedProvider(
            split_raw={"exercises": [{"position": 1, "name": "Bench Press", "anchor": "Bench Press"}]},
            shell_raw={"date": "2026-05-12"},
            exercise_raw_by_position={
                1: _exercise_raw(1, "Bench Press", uncertain_fields=["sets.0.rpe"]),
            },
        )

        extract = assemble("text", provider=provider)

        assert extract.uncertain_fields == ["exercises.0.sets.0.rpe"]

    def test_shell_uncertain_fields_pass_through_unprefixed(self) -> None:
        provider = ScriptedProvider(
            split_raw={"exercises": []},
            shell_raw={"date": "2026-05-12", "uncertain_fields": ["session_duration_minutes"]},
            exercise_raw_by_position={},
        )

        extract = assemble("text", provider=provider)

        assert extract.uncertain_fields == ["session_duration_minutes"]
        assert extract.exercises == []

    def test_failed_worker_becomes_flagged_placeholder_not_a_crash(self) -> None:
        text = (
            "Bench Press\nSets:\n1. 80kg x 8\n\n"
            "Overhead Press\nSets:\n1. 40kg x 8\n\n"
            "Lat Pulldown\nSets:\n1. 100kg x 8\n"
        )
        provider = ScriptedProvider(
            split_raw={
                "exercises": [
                    {"position": 1, "name": "Bench Press", "anchor": "Bench Press"},
                    {"position": 2, "name": "Overhead Press", "anchor": "Overhead Press"},
                    {"position": 3, "name": "Lat Pulldown", "anchor": "Lat Pulldown"},
                ]
            },
            shell_raw={"date": "2026-05-12"},
            exercise_raw_by_position={
                1: _exercise_raw(1, "Bench Press"),
                # position 2 deliberately missing -> ScriptedProvider raises LLMParserError
                3: _exercise_raw(3, "Lat Pulldown"),
            },
        )

        extract = assemble(text, provider=provider)

        assert [e.name for e in extract.exercises] == ["Bench Press", "Overhead Press", "Lat Pulldown"]
        assert extract.exercises[1].sets is None
        assert "Extraction failed" in (extract.exercises[1].notes or "")
        assert any(
            "Exercise 2 (Overhead Press) failed to extract" in w for w in extract.warnings
        )
        # The other two exercises still extracted cleanly despite the failure.
        assert extract.exercises[0].sets is not None
        assert extract.exercises[2].sets is not None


class TestAssembleChunking:
    """Covers the deterministic pre-chunking added to fix the "lost in the middle"
    position-drift/missing-sets problem found during live E2E testing: each worker should get
    an isolated, pre-sliced excerpt for its own exercise rather than the full document,
    with a graceful fallback (full text + a warning, not a crash) when an anchor can't be
    located verbatim."""

    def test_each_worker_receives_its_own_isolated_chunk_not_the_full_text(self) -> None:
        text = (
            "Bench Press\nSets:\n1. 80kg x 8\n\n"
            "Overhead Press\nSets:\n1. 40kg x 8\n\n"
            "Lat Pulldown\nSets:\n1. 100kg x 8\n"
        )
        provider = ScriptedProvider(
            split_raw={
                "exercises": [
                    {"position": 1, "name": "Bench Press", "anchor": "Bench Press"},
                    {"position": 2, "name": "Overhead Press", "anchor": "Overhead Press"},
                    {"position": 3, "name": "Lat Pulldown", "anchor": "Lat Pulldown"},
                ]
            },
            shell_raw={"date": "2026-05-12"},
            exercise_raw_by_position={
                1: _exercise_raw(1, "Bench Press"),
                2: _exercise_raw(2, "Overhead Press"),
                3: _exercise_raw(3, "Lat Pulldown"),
            },
        )

        assemble(text, provider=provider)

        # Each worker got an isolated excerpt, not the full document with everyone else's data
        # mixed in — proven by the OTHER exercises' distinctive weight being absent.
        assert "100kg" not in provider.worker_texts[1]
        assert "80kg" not in provider.worker_texts[3]

    def test_anchor_not_found_falls_back_to_full_text_with_a_warning_not_a_crash(self) -> None:
        text = "Bench Press\nSets:\n1. 80kg x 8\n"
        provider = ScriptedProvider(
            split_raw={
                "exercises": [
                    # This anchor does not appear verbatim in `text` — model paraphrased it.
                    {"position": 1, "name": "Bench Press", "anchor": "Bench press (paraphrased)"},
                ]
            },
            shell_raw={"date": "2026-05-12"},
            exercise_raw_by_position={
                1: _exercise_raw(1, "Bench Press", sets=[
                    {"number": 1, "source_line": "1. 80kg x 8", "weight_kg": 80.0, "reps": "8"}
                ]),
            },
        )

        extract = assemble(text, provider=provider)

        assert extract.exercises[0].name == "Bench Press"
        assert extract.exercises[0].sets is not None
        # Fell back to the full document rather than crashing or dropping the exercise.
        assert "80kg" in provider.worker_texts[1]
        assert any("could not isolate its text" in w for w in extract.warnings)

    def test_exercise_number_is_forced_to_the_splitters_position_not_the_workers_own_report(
        self,
    ) -> None:
        """The splitter already knows the correct position — assemble() should trust that over
        whatever number the worker itself reports, removing one more thing the model can get
        wrong (independent of chunking)."""
        provider = ScriptedProvider(
            split_raw={"exercises": [{"position": 3, "name": "Bench Press", "anchor": "Bench Press"}]},
            shell_raw={"date": "2026-05-12"},
            exercise_raw_by_position={
                # Worker reports the wrong number (1) for what the splitter said was position 3.
                3: _exercise_raw(1, "Bench Press"),
            },
        )

        extract = assemble("text", provider=provider)

        assert extract.exercises[0].number == 3


class TestAssembleSixExerciseRegression:
    """Regression coverage for the drop bug the orchestration refactor exists to fix: a single
    monolithic LLM call on this real 6-exercise session silently lost the RPE/remark on the
    tail exercises across repeated live runs (root-caused to non-deterministic sampling, but
    the split-call design is the structural fix — one call per exercise can't lose another
    exercise's data). Confirms the assembler itself never drops an exercise regardless of how
    many worker calls it makes.

    Scope note: this covers the *assembler*, not extraction accuracy. Each scripted worker
    response supplies its own last-set RPE, so what's proven here is that assemble() keeps all
    six exercises, in order, and attaches each worker's answer to the right one. Whether a real
    model reads those RPEs correctly out of the fixture is measured by scripts/eval_arms.py
    against real sessions, not here."""

    FIXTURE = FIXTURES_DIR / "programmed_push_pull_session_with_remarks.md"

    def test_all_six_exercises_and_their_last_set_rpe_survive(self) -> None:
        text = self.FIXTURE.read_text(encoding="utf-8")

        names = [
            "Bench Press",
            "Incline DB Press",
            "Chest Supported Rows",
            "Lat Pulldown",
            "Lateral Raise",
            "Triceps Pushdown",
        ]
        # Each exercise's trailing "RPE: N" (or "N-M") remark applies to its LAST set only,
        # per the design-session convention (upper bound taken for a range). Chest Supported
        # Rows genuinely has no RPE remark at all in the real fixture.
        rpe_by_position = {1: 7.0, 2: 7.0, 3: None, 4: 8.0, 5: 8.0, 6: 8.0}
        # Two sets each; the RPE rides the last one, mirroring the convention above.
        def _sets_with_last_rpe(rpe: float | None) -> list[dict[str, Any]]:
            return [
                {"number": 1, "source_line": "1. 60kg x 8",
                 "weight_kg": 60.0, "reps": "8"},
                {"number": 2, "source_line": "2. 60kg x 8",
                 "weight_kg": 60.0, "reps": "8", "rpe": rpe},
            ]

        split_raw = {
            "exercises": [
                {"position": i + 1, "name": name, "anchor": name} for i, name in enumerate(names)
            ]
        }
        shell_raw = {
            "date": "3000-05-11",
            "program": "Bodybuilding Transformation System",
            "phase": 1,
            "week": 1,
            "focus": "Powerlifting and Mobility",
            "session_duration_minutes": 101,
        }
        exercise_raw_by_position = {
            i: _exercise_raw(i, name, sets=_sets_with_last_rpe(rpe_by_position[i]))
            for i, name in enumerate(names, start=1)
        }

        provider = ScriptedProvider(split_raw, shell_raw, exercise_raw_by_position)

        extract = assemble(text, provider=provider)

        assert [e.name for e in extract.exercises] == names
        assert len(extract.exercises) == 6
        assert provider.worker_tool_names == [WORKER_TOOL_NAME] * 6
        # audit() legitimately flags the real fixture's weights as missing, because the scripted
        # worker responses above carry a synthetic 60kg spine rather than mirroring the file.
        # That's the drop-check working, not a failure — so assert only that the *assembler*
        # raised nothing: no exercise failed to extract, none fell back to the full document.
        assert not [w for w in extract.warnings if "failed to extract" in w or "isolate" in w]
        for i, name in enumerate(names):
            expected_rpe = rpe_by_position[i + 1]
            last_set = extract.exercises[i].sets[-1]
            assert last_set.rpe == expected_rpe, f"{name} lost its last-set RPE"


class TestAssembleSourceLines:
    """assemble() runs the two source-line checks per exercise, and the projection keeps
    extraction-only fields out of the plain Exercise it hands downstream."""

    TEXT = "Bench Press\nSets:\n1. 80kg x 8\n"
    SPLIT = {"exercises": [{"position": 1, "name": "Bench Press", "anchor": "Bench Press"}]}

    def _run(self, sets: list[dict[str, Any]]) -> Any:
        provider = ScriptedProvider(
            split_raw=self.SPLIT,
            shell_raw={"date": "2026-05-12"},
            exercise_raw_by_position={1: _exercise_raw(1, "Bench Press", sets=sets)},
        )
        return assemble(self.TEXT, provider=provider)

    def test_source_lines_do_not_reach_the_plain_exercise(self) -> None:
        extract = self._run([
            {"number": 1, "source_line": "1. 80kg x 8", "weight_kg": 80.0, "reps": "8"}
        ])
        assert not hasattr(extract.exercises[0].sets[0], "source_line")

    def test_a_real_source_line_produces_no_warning(self) -> None:
        extract = self._run([
            {"number": 1, "source_line": "1. 80kg x 8", "weight_kg": 80.0, "reps": "8"}
        ])
        assert extract.warnings == []

    def test_an_invented_source_line_is_reported_against_its_exercise(self) -> None:
        extract = self._run([
            {"number": 1, "source_line": "1. 500kg x 1", "weight_kg": 500.0, "reps": "1"}
        ])
        assert any(
            "Exercise 1 (Bench Press)" in w and "isn't in the text" in w
            for w in extract.warnings
        )

    def test_an_empty_source_line_is_reported(self) -> None:
        extract = self._run([
            {"number": 1, "source_line": "  ", "weight_kg": 80.0, "reps": "8"}
        ])
        assert any("set 1 has no source line recorded" in w for w in extract.warnings)

    def test_rep_text_that_cannot_be_read_is_reported(self) -> None:
        extract = self._run([
            {"number": 1, "source_line": "1. 80kg x 8", "weight_kg": 80.0, "reps": "a few"}
        ])
        assert any("a few" in w for w in extract.warnings)
        assert extract.exercises[0].sets[0].rep_count is None
