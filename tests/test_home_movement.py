"""
Home-movement intake: model-contract tests for the conventions this feature
relies on (see home-movement-plan.md). No DB, no live LLM call — these confirm
the schema already supports the shapes the SYSTEM_PROMPT conventions produce,
and guard the prompt text itself against silent regression.
"""
from __future__ import annotations

from typing import Any

from traininglogs.agent.llm_parser import SYSTEM_PROMPT, TrainingLogLLMExtract, parse
from traininglogs.processor.processor import build_session_from_extract
from pathlib import Path


class StubProvider:
    def __init__(self, raw: dict) -> None:
        self._raw = raw

    def extract(self, text: str, tool_schema: dict) -> dict:
        return self._raw


HOME_MOVEMENT_RAW: dict[str, Any] = {
    "date": "2026-07-19",
    "program": "home-movement",
    "focus": "Skills + Core",
    "session_duration_minutes": 55,
    "exercises": [
        {
            "number": 1,
            "name": "Juggling 3-Ball Cascade",
            "modality": "bodyweight",
            "tags": ["balance_control"],
            "sets": [
                {"number": 1, "rep_count": {"full": 38, "partial": 0},
                 "notes": "best of 4 runs (22, 31, 38, 29)"},
            ],
        },
        {
            "number": 2,
            "name": "Reaction Drill",
            "modality": "bodyweight",
            "sets": [
                {"number": 1, "notes": "avg 245ms, best 198ms; first block avg 290ms"},
            ],
        },
        {
            "number": 3,
            "name": "L-Sit on Parallettes",
            "modality": "bodyweight",
            "sets": [
                {"number": 1, "duration_seconds": 18, "rpe": None},
                {"number": 2, "duration_seconds": 16},
                {"number": 3, "duration_seconds": 15},
                {"number": 4, "duration_seconds": 12},
                {"number": 5, "duration_seconds": 10, "rpe": 8.0,
                 "notes": "legs dropping"},
            ],
        },
        {
            "number": 4,
            "name": "Kettlebell Swing",
            "modality": "kettlebell",
            "sets": [
                {"number": 1, "weight_kg": 20.0, "rep_count": {"full": 15}},
                {"number": 2, "weight_kg": 20.0, "rep_count": {"full": 15}},
                {"number": 3, "weight_kg": 20.0, "rep_count": {"full": 15}},
            ],
        },
    ],
}


class TestHomeMovementSchemaFit:
    """The existing model already holds every shape the conventions produce."""

    def test_program_without_phase_or_week_is_valid(self) -> None:
        extract = TrainingLogLLMExtract.model_validate(HOME_MOVEMENT_RAW)
        assert extract.program == "home-movement"
        assert extract.phase is None
        assert extract.week is None

    def test_skill_run_stored_as_rep_count(self) -> None:
        extract = TrainingLogLLMExtract.model_validate(HOME_MOVEMENT_RAW)
        juggling_set = extract.exercises[0].sets[0]
        assert juggling_set.rep_count.full == 38
        assert "best of 4 runs" in juggling_set.notes

    def test_reaction_time_lives_in_notes_not_numeric_fields(self) -> None:
        extract = TrainingLogLLMExtract.model_validate(HOME_MOVEMENT_RAW)
        reaction_set = extract.exercises[1].sets[0]
        assert reaction_set.duration_seconds is None
        assert reaction_set.rep_count is None
        assert "245ms" in reaction_set.notes

    def test_static_hold_stored_as_duration(self) -> None:
        extract = TrainingLogLLMExtract.model_validate(HOME_MOVEMENT_RAW)
        holds = extract.exercises[2].sets
        assert [s.duration_seconds for s in holds] == [18, 16, 15, 12, 10]
        assert holds[0].failure_technique is None  # planned hold, not a failure technique

    def test_home_kettlebell_lift_stored_as_weight_and_reps(self) -> None:
        extract = TrainingLogLLMExtract.model_validate(HOME_MOVEMENT_RAW)
        kb_set = extract.exercises[3].sets[0]
        assert kb_set.weight_kg == 20.0
        assert kb_set.rep_count.full == 15

    def test_build_session_from_extract_accepts_phaseless_program(self, tmp_path: Path) -> None:
        extract = TrainingLogLLMExtract.model_validate(HOME_MOVEMENT_RAW)
        md_path = tmp_path / "home_movement_session.md"
        md_path.write_text("stub")
        session = build_session_from_extract(extract, md_path, inputs_root=tmp_path)
        assert session.program == "home-movement"
        assert session.phase is None
        assert session.week is None
        assert session.session_id.startswith("2026-07-19-")

    def test_skill_attempt_clean_vs_failed_maps_to_full_partial(self) -> None:
        """Same convention as juggling/reaction, but for skill attempts (e.g.
        muscle-up tries) where some attempts succeed and some don't — this
        applies inside formal programs too, not just ad-hoc home-movement
        sessions, since it's a per-exercise rule, not a program-level one."""
        raw = dict(HOME_MOVEMENT_RAW)
        raw["exercises"] = [
            {
                "number": 1,
                "name": "Ring Muscle-Up Transition",
                "modality": "rings",
                "sets": [
                    {"number": 1, "rep_count": {"full": 2, "partial": 3},
                     "notes": "band-assisted"},
                ],
            }
        ]
        extract = TrainingLogLLMExtract.model_validate(raw)
        skill_set = extract.exercises[0].sets[0]
        assert skill_set.rep_count.full == 2
        assert skill_set.rep_count.partial == 3
        assert skill_set.rep_count.total_reps == 5

    def test_movement_skill_exercise_valid_with_formal_phase_and_week(self) -> None:
        """A calisthenics/rings exercise mixed into a real structured program
        (phase/week given) must validate the same way as in an ad-hoc session —
        these conventions are program-agnostic."""
        raw = dict(HOME_MOVEMENT_RAW)
        raw["program"] = None
        raw["phase"] = 3
        raw["week"] = 12
        raw["exercises"] = [
            {
                "number": 1,
                "name": "Ring Dips",
                "modality": "rings",
                "sets": [{"number": 1, "rep_count": {"full": 10, "partial": 0}}],
            }
        ]
        extract = TrainingLogLLMExtract.model_validate(raw)
        assert extract.phase == 3
        assert extract.week == 12
        assert extract.exercises[0].sets[0].rep_count.full == 10


class TestParseWithHomeMovementFixture:
    def test_parse_returns_valid_extract(self) -> None:
        extract = parse("stub text", provider=StubProvider(HOME_MOVEMENT_RAW))
        assert len(extract.exercises) == 4
        assert extract.program == "home-movement"


class TestSystemPromptConventions:
    """Guard the prompt text itself — these lines are what makes the LLM produce
    the shapes asserted above. If someone edits SYSTEM_PROMPT and these vanish,
    the schema tests above still pass but real extraction will silently regress."""

    def test_prompt_defines_home_movement_program_default(self) -> None:
        assert "home-movement" in SYSTEM_PROMPT

    def test_prompt_defines_skill_run_as_reps(self) -> None:
        assert "one set" in SYSTEM_PROMPT
        assert "catches" in SYSTEM_PROMPT

    def test_prompt_defines_reaction_time_in_notes(self) -> None:
        assert "Reaction-time drills" in SYSTEM_PROMPT
        assert "Never put milliseconds into" in SYSTEM_PROMPT

    def test_prompt_disambiguates_tap_count_from_duration(self) -> None:
        assert "it is NOT a duration" in SYSTEM_PROMPT

    def test_prompt_defines_static_holds_as_duration(self) -> None:
        assert "Static holds" in SYSTEM_PROMPT
        assert "Do not use the StaticHold failure technique for planned holds" in SYSTEM_PROMPT

    def test_prompt_defines_skill_attempt_full_partial_mapping(self) -> None:
        assert "Skill attempts at a specific move" in SYSTEM_PROMPT
        assert "rep_count.full = attempts that were completed cleanly" in SYSTEM_PROMPT
        assert "rep_count.partial = attempts that were tried but not completed" in SYSTEM_PROMPT

    def test_prompt_does_not_default_to_home_movement_when_phase_week_given(self) -> None:
        """Regression guard: a session with phase/week but no explicit program name
        is part of a real program whose name lives outside the file (usually the
        directory path) — it must not get silently mislabeled home-movement."""
        assert "leave program unset" in SYSTEM_PROMPT
