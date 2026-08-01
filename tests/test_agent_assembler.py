"""Integration tests for assemble() — the split-extraction glue: segment() -> extract_shell()
-> one extract_exercise() per position -> TrainingLogLLMExtract. Fake providers only, no real
LLM calls."""
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
    """Dispatches by tool_name (splitter/shell/worker); worker calls are further dispatched
    by the position number embedded in the prompt text, since all three call kinds share the
    same ExtractionProvider.extract() method."""

    def __init__(
        self,
        split_raw: dict[str, Any],
        shell_raw: dict[str, Any],
        exercise_raw_by_position: dict[int, dict[str, Any]],
    ) -> None:
        self._split_raw = split_raw
        self._shell_raw = shell_raw
        self._exercise_raw_by_position = exercise_raw_by_position
        self.worker_calls: list[int] = []

    def extract(
        self, text: str, tool_schema: dict, system_prompt: str, tool_name: str, tool_description: str
    ) -> dict:
        if tool_name == SEGMENT_TOOL_NAME:
            return self._split_raw
        if tool_name == SHELL_TOOL_NAME:
            return self._shell_raw
        if tool_name == WORKER_TOOL_NAME:
            position = int(text.split("Extract exercise number ")[1].split(".")[0])
            self.worker_calls.append(position)
            raw = self._exercise_raw_by_position.get(position)
            if raw is None:
                raise LLMParserError(f"no scripted response for position {position}")
            return raw
        raise AssertionError(f"unexpected tool_name: {tool_name}")


def _exercise_raw(number: int, name: str, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "exercise": {
            "number": number,
            "name": name,
            "sets": [{"number": 1, "weight_kg": 50.0, "rep_count": {"full": 8, "partial": 0}}],
        },
        "uncertain_fields": [],
    }
    base.update(overrides)
    return base


class TestAssembleIntegration:
    def test_glues_shell_and_exercises_in_order(self) -> None:
        provider = ScriptedProvider(
            split_raw={
                "exercises": [
                    {"position": 1, "name": "Bench Press"},
                    {"position": 2, "name": "Overhead Press"},
                ]
            },
            shell_raw={"date": "2026-05-12", "focus": "Upper", "session_duration_minutes": 60},
            exercise_raw_by_position={
                1: _exercise_raw(1, "Bench Press"),
                2: _exercise_raw(2, "Overhead Press"),
            },
        )

        extract = assemble("some session text", provider=provider)

        assert extract.date == "2026-05-12"
        assert extract.focus == "Upper"
        assert [e.name for e in extract.exercises] == ["Bench Press", "Overhead Press"]
        assert extract.warnings == []
        assert provider.worker_calls == [1, 2]

    def test_worker_uncertain_fields_get_prefixed_with_exercise_index(self) -> None:
        provider = ScriptedProvider(
            split_raw={"exercises": [{"position": 1, "name": "Bench Press"}]},
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
        provider = ScriptedProvider(
            split_raw={
                "exercises": [
                    {"position": 1, "name": "Bench Press"},
                    {"position": 2, "name": "Overhead Press"},
                    {"position": 3, "name": "Lat Pulldown"},
                ]
            },
            shell_raw={"date": "2026-05-12"},
            exercise_raw_by_position={
                1: _exercise_raw(1, "Bench Press"),
                # position 2 deliberately missing -> ScriptedProvider raises LLMParserError
                3: _exercise_raw(3, "Lat Pulldown"),
            },
        )

        extract = assemble("text", provider=provider)

        assert [e.name for e in extract.exercises] == ["Bench Press", "Overhead Press", "Lat Pulldown"]
        assert extract.exercises[1].sets is None
        assert "Extraction failed" in (extract.exercises[1].notes or "")
        assert len(extract.warnings) == 1
        assert "Exercise 2 (Overhead Press) failed to extract" in extract.warnings[0]
        # The other two exercises still extracted cleanly despite the failure.
        assert extract.exercises[0].sets is not None
        assert extract.exercises[2].sets is not None


class TestAssembleSixExerciseRegression:
    """Regression coverage for the drop bug the orchestration refactor exists to fix: a single
    monolithic LLM call on this real 6-exercise session silently lost the RPE/remark on the
    tail exercises across repeated live runs (root-caused to non-deterministic sampling, but
    the split-call design is the structural fix — one call per exercise can't lose another
    exercise's data). Confirms the assembler itself never drops an exercise regardless of how
    many worker calls it makes."""

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
        # per the design-session convention (upper bound taken for a range).
        rpe_by_position = {1: 7.0, 2: 7.0, 3: None, 4: 8.0, 5: 8.0, 6: 8.0}

        split_raw = {
            "exercises": [{"position": i + 1, "name": name} for i, name in enumerate(names)]
        }
        shell_raw = {
            "date": "3000-05-11",
            "program": "Bodybuilding Transformation System",
            "phase": 1,
            "week": 1,
            "focus": "Powerlifting and Mobility",
            "session_duration_minutes": 101,
        }
        exercise_raw_by_position = {}
        for i, name in enumerate(names, start=1):
            n_sets = 4 if i == 1 else 3
            sets = [
                {"number": j + 1, "weight_kg": 90.0, "rep_count": {"full": 8, "partial": 0}}
                for j in range(n_sets)
            ]
            rpe = rpe_by_position[i]
            uncertain: list[str] = []
            if rpe is not None:
                sets[-1]["rpe"] = rpe
                uncertain.append(f"sets.{n_sets - 1}.rpe")
            exercise_raw_by_position[i] = _exercise_raw(i, name, uncertain_fields=uncertain)
            exercise_raw_by_position[i]["exercise"]["sets"] = sets

        provider = ScriptedProvider(split_raw, shell_raw, exercise_raw_by_position)

        extract = assemble(text, provider=provider)

        assert [e.name for e in extract.exercises] == names
        assert len(extract.exercises) == 6
        assert extract.warnings == []
        for i, name in enumerate(names):
            expected_rpe = rpe_by_position[i + 1]
            last_set = extract.exercises[i].sets[-1]
            assert last_set.rpe == expected_rpe, f"{name} lost its last-set RPE"
