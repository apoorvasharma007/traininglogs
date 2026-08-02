"""Integration tests for assemble() — the split-extraction glue: segment() -> extract_shell()
-> per-position parse_exercise_block() gate -> extract_exercise_labels() (parsed path) or
extract_exercise() (fallback path) -> TrainingLogLLMExtract. Fake providers only, no real LLM
calls.

Most texts in this file use clean "N. weight x reps" set lines, which parse_exercise_block()
parses successfully — so most worker calls below go through the LABELS_TOOL_NAME path, not
WORKER_TOOL_NAME, and their scripted responses are shaped as ExerciseLabelsExtract (name +
classification only, no sets/warmup_sets — see _labels_raw). Only texts that can't isolate a
chunk at all (anchor not found) still exercise the old full-extraction path."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from traininglogs.agent.extraction import (
    LABELS_TOOL_NAME,
    SEGMENT_TOOL_NAME,
    SHELL_TOOL_NAME,
    WORKER_TOOL_NAME,
    assemble,
)
from traininglogs.agent.schemas import LLMParserError

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "valid"


class ScriptedProvider:
    """Dispatches by tool_name (splitter/shell/either worker tool). Worker calls (whichever
    tool_name they use) are dispatched by call order, not by the position number embedded in
    the prompt text: assemble() passes 1 (the chunk-local position) for every
    successfully-isolated chunk, not the splitter's global split_position — so every chunked
    worker call's prompt says "exercise number 1" no matter which real exercise it's for, and
    parsing that number can't tell calls apart. assemble() calls workers in split order, one
    per entry, so the Nth worker call always corresponds to the Nth entry in
    split_raw["exercises"] — that ordering, not the prompt text, is what identifies each call's
    split_position here. Which tool_name is used for a given position isn't controlled by this
    class at all — it's decided by whether parse_exercise_block() succeeds on that position's
    real (isolated) chunk text, so the caller must supply a raw response of the right shape for
    whichever path a given text will actually take."""

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
        self, text: str, tool_schema: dict, system_prompt: str, tool_name: str, tool_description: str
    ) -> dict:
        if tool_name == SEGMENT_TOOL_NAME:
            return self._split_raw
        if tool_name == SHELL_TOOL_NAME:
            return self._shell_raw
        if tool_name in (WORKER_TOOL_NAME, LABELS_TOOL_NAME):
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
    """Full-extraction-path (ExerciseExtract) fixture — only meaningful for a position whose
    chunk can't be isolated at all (anchor not found), since that's the only case that still
    calls extract_exercise() instead of extract_exercise_labels()."""
    base: dict[str, Any] = {
        "number": number,
        "name": name,
        "sets": [{"number": 1, "weight_kg": 50.0, "rep_count": {"full": 8, "partial": 0}}],
        "uncertain_fields": [],
    }
    base.update(overrides)
    return base


def _labels_raw(name: str, **overrides: Any) -> dict[str, Any]:
    """Parsed-path (ExerciseLabelsExtract) fixture — no sets/warmup_sets fields exist on this
    schema at all, so there's nothing to specify for them; parse_exercise_block() supplies the
    numeric spine directly from the real chunk text."""
    base: dict[str, Any] = {"name": name, "uncertain_fields": []}
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
                1: _labels_raw("Bench Press"),
                2: _labels_raw("Overhead Press"),
            },
        )

        extract = assemble(SAMPLE_TWO_EXERCISE_TEXT, provider=provider)

        assert extract.date == "2026-05-12"
        assert extract.focus == "Upper"
        assert [e.name for e in extract.exercises] == ["Bench Press", "Overhead Press"]
        # Both blocks parse cleanly (SAMPLE_TWO_EXERCISE_TEXT's set lines are regular), so both
        # weights below came from parse_exercise_block(), not the scripted labels response.
        assert extract.exercises[0].sets[0].weight_kg == 80.0
        assert extract.exercises[1].sets[0].weight_kg == 40.0
        assert extract.warnings == []
        assert provider.worker_calls == [1, 2]
        assert provider.worker_tool_names == [LABELS_TOOL_NAME, LABELS_TOOL_NAME]

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
                1: _labels_raw("Bench Press"),
                # position 2 deliberately missing -> ScriptedProvider raises LLMParserError
                3: _labels_raw("Lat Pulldown"),
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
                1: _labels_raw("Bench Press"),
                2: _labels_raw("Overhead Press"),
                3: _labels_raw("Lat Pulldown"),
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
                    {"number": 1, "weight_kg": 80.0, "rep_count": {"full": 8, "partial": 0}}
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

    All 6 of this real fixture's exercises parse cleanly via parse_exercise_block() (confirmed
    in tests/test_agent_exercise_block.py), so every exercise's numeric spine — sets,
    warmup_sets, and last-set RPE placement — comes directly from the real fixture text below,
    not from anything in the scripted labels responses (which only supply each exercise's
    name). This is a stronger test than before this fix: it no longer needs to hand-construct
    weights/RPE mirroring the fixture, because the parser reads the fixture itself."""

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
        exercise_raw_by_position = {i: _labels_raw(name) for i, name in enumerate(names, start=1)}

        provider = ScriptedProvider(split_raw, shell_raw, exercise_raw_by_position)

        extract = assemble(text, provider=provider)

        assert [e.name for e in extract.exercises] == names
        assert len(extract.exercises) == 6
        assert extract.warnings == []
        assert provider.worker_tool_names == [LABELS_TOOL_NAME] * 6
        for i, name in enumerate(names):
            expected_rpe = rpe_by_position[i + 1]
            last_set = extract.exercises[i].sets[-1]
            assert last_set.rpe == expected_rpe, f"{name} lost its last-set RPE"


class TestAssembleReproducesOriginalFailures:
    """End-to-end regression tests for the three value-level LLM failures found in live E2E
    testing that motivated the extraction-accuracy fix (see extraction-accuracy-plan.md). Each
    scripted labels response omits the very information the original bad LLM call got wrong —
    proving the fix removes the failure by construction (there's no field left for the LLM to
    misreport), not by hoping a better-behaved model happens to get it right."""

    def test_weight_and_warmup_are_never_dropped(self) -> None:
        """Original failure: weight dropped from all three Incline DB Press sets, plus its
        whole warmup section, despite reps/RPE on the same lines being correct. The labels
        schema has no sets/warmup_sets fields at all, so there's nothing for the LLM to drop."""
        text = (
            "Incline DB Press\nWarmup:\n1. 40kg x 4\n2. 60kg x 4\nSets:\n"
            "1. 80kg x 8\n2. 80kg x 9\n3. 80kg x 6\n\nRemarks:\n1. RPE: 6-7.\n"
        )
        provider = ScriptedProvider(
            split_raw={
                "exercises": [
                    {"position": 1, "name": "Incline DB Press", "anchor": "Incline DB Press"}
                ]
            },
            shell_raw={"date": "2026-05-12"},
            exercise_raw_by_position={1: _labels_raw("Incline DB Press")},
        )

        extract = assemble(text, provider=provider)

        exercise = extract.exercises[0]
        assert [s.weight_kg for s in exercise.sets] == [80.0, 80.0, 80.0]
        assert [w.weight_kg for w in exercise.warmup_sets] == [40.0, 60.0]

    def test_lat_pulldown_rpe_defaults_to_last_set_not_first(self) -> None:
        """Original failure: an exercise-level RPE mentioned once in remarks landed on set 1
        instead of set 3. The scripted labels response below deliberately omits
        exercise_rpe_target_set (the field a model would use to name a different set) —
        placement defaults to the last set by construction, not by LLM judgment."""
        text = (
            "Lat Pulldown\nWarmup:\n1. 45kg x 5\nSets:\n"
            "1. 100kg x 8\n2. 100kg x 8\n3. 100kg x 8\n\nRemarks:\n1. RPE: 8\n"
        )
        provider = ScriptedProvider(
            split_raw={
                "exercises": [{"position": 1, "name": "Lat Pulldown", "anchor": "Lat Pulldown"}]
            },
            shell_raw={"date": "2026-05-12"},
            exercise_raw_by_position={1: _labels_raw("Lat Pulldown")},
        )

        extract = assemble(text, provider=provider)

        sets = extract.exercises[0].sets
        assert sets[0].rpe is None
        assert sets[1].rpe is None
        assert sets[2].rpe == 8.0

    def test_lateral_raise_working_sets_land_in_sets_not_warmup_sets(self) -> None:
        """Original failure: three working sets under a Sets: header got filed into
        warmup_sets, leaving sets empty. Structurally impossible now — the parser reads the
        section header itself, so there's no LLM decision about which field these numbers
        belong in at all. This is also the fixture's one exercise with an empty Warmup: line
        immediately before Sets:."""
        text = (
            "Lateral Raise\nWarmup:\nSets:\n1. 10kg x 15\n2. 10kg x 15\n3. 10kg x 15\n\n"
            "Remarks:\n1. RPE: 8\n"
        )
        provider = ScriptedProvider(
            split_raw={
                "exercises": [{"position": 1, "name": "Lateral Raise", "anchor": "Lateral Raise"}]
            },
            shell_raw={"date": "2026-05-12"},
            exercise_raw_by_position={1: _labels_raw("Lateral Raise")},
        )

        extract = assemble(text, provider=provider)

        exercise = extract.exercises[0]
        assert [s.weight_kg for s in exercise.sets] == [10.0, 10.0, 10.0]
        assert not exercise.warmup_sets
