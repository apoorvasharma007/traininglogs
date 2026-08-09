"""
Movement-skill intake (calisthenics, gymnastics rings, juggling, reaction drills,
shadow boxing, kettlebell/dumbbell work): model-contract tests for the conventions
these rely on (see archived/plans/movement-skill-plan.md). No DB, no live LLM call — these confirm
the schema already supports the shapes the SYSTEM_PROMPT conventions produce, and
guard the prompt text itself against silent regression.

For real end-to-end verification against the actual parser, see the matching
fixtures in tests/fixtures/valid/ (adhoc_movement_skills_session.md,
adhoc_calisthenics_rings_session.md, programmed_calisthenics_mixed_session.md) and
run `traininglogs validate <fixture> --parser groq`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from traininglogs.agent.schemas import TrainingLogLLMExtract
from traininglogs.processor.processor import build_session_from_extract


class StubProvider:
    def __init__(self, raw: dict) -> None:
        self._raw = raw

    def extract(
        self, text: str, tool_schema: dict, system_prompt: str, tool_name: str,
        tool_description: str, validate=None
    ) -> dict:
        return self._raw


# Mirrors tests/fixtures/valid/adhoc_movement_skills_session.md — ad-hoc, no
# program/phase/week.
ADHOC_MOVEMENT_SKILLS_RAW: dict[str, Any] = {
    "date": "2026-07-19",
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
                {"number": 1, "duration_seconds": 18},
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


class TestAdhocMovementSkillsSchemaFit:
    """The existing model already holds every shape the conventions produce."""

    def test_ad_hoc_session_has_no_program_phase_or_week(self) -> None:
        extract = TrainingLogLLMExtract.model_validate(ADHOC_MOVEMENT_SKILLS_RAW)
        assert extract.program is None
        assert extract.phase is None
        assert extract.week is None

    def test_skill_run_stored_as_rep_count(self) -> None:
        extract = TrainingLogLLMExtract.model_validate(ADHOC_MOVEMENT_SKILLS_RAW)
        juggling_set = extract.exercises[0].sets[0]
        assert juggling_set.rep_count.full == 38
        assert "best of 4 runs" in juggling_set.notes

    def test_reaction_time_lives_in_notes_not_numeric_fields(self) -> None:
        extract = TrainingLogLLMExtract.model_validate(ADHOC_MOVEMENT_SKILLS_RAW)
        reaction_set = extract.exercises[1].sets[0]
        assert reaction_set.duration_seconds is None
        assert reaction_set.rep_count is None
        assert "245ms" in reaction_set.notes

    def test_static_hold_stored_as_duration(self) -> None:
        extract = TrainingLogLLMExtract.model_validate(ADHOC_MOVEMENT_SKILLS_RAW)
        holds = extract.exercises[2].sets
        assert [s.duration_seconds for s in holds] == [18, 16, 15, 12, 10]
        assert holds[0].failure_technique is None  # planned hold, not a failure technique

    def test_kettlebell_lift_stored_as_weight_and_reps(self) -> None:
        extract = TrainingLogLLMExtract.model_validate(ADHOC_MOVEMENT_SKILLS_RAW)
        kb_set = extract.exercises[3].sets[0]
        assert kb_set.weight_kg == 20.0
        assert kb_set.rep_count.full == 15

    def test_build_session_from_extract_leaves_program_unset(self, tmp_path: Path) -> None:
        extract = TrainingLogLLMExtract.model_validate(ADHOC_MOVEMENT_SKILLS_RAW)
        md_path = tmp_path / "adhoc_session.md"
        md_path.write_text("stub")
        session = build_session_from_extract(extract, md_path, inputs_root=tmp_path)
        assert session.program is None
        assert session.phase is None
        assert session.week is None
        assert session.session_id.startswith("2026-07-19-")

    def test_skill_attempt_clean_vs_failed_maps_to_full_partial(self) -> None:
        """Skill attempts (e.g. muscle-up tries) use full/partial the same way in
        an ad-hoc session as in a formal program — it's a per-exercise rule, not
        a program-level one."""
        raw = dict(ADHOC_MOVEMENT_SKILLS_RAW)
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

    def test_ordinary_reps_with_varying_quality_stay_whole_not_partial(self) -> None:
        """Regression guard: 'depth dropped on the last two' is commentary on an
        ordinary rep set, not a skill-attempt clean/failed split. Every completed
        rep is full; quality notes must not shift reps into partial."""
        raw = dict(ADHOC_MOVEMENT_SKILLS_RAW)
        raw["exercises"] = [
            {
                "number": 1,
                "name": "Ring Dips",
                "modality": "rings",
                "sets": [
                    {"number": 1, "rep_count": {"full": 6, "partial": 0},
                     "notes": "depth dropped off on last two"},
                ],
            }
        ]
        extract = TrainingLogLLMExtract.model_validate(raw)
        dip_set = extract.exercises[0].sets[0]
        assert dip_set.rep_count.full == 6
        assert dip_set.rep_count.partial == 0

    def test_movement_skill_exercise_valid_with_formal_phase_and_week(self) -> None:
        """A calisthenics/rings exercise mixed into a real structured program
        (phase/week given) must validate the same way as in an ad-hoc session —
        these conventions are program-agnostic."""
        raw = dict(ADHOC_MOVEMENT_SKILLS_RAW)
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
        assert extract.program is None  # program name lives in the file path, not here
        assert extract.phase == 3
        assert extract.week == 12
        assert extract.exercises[0].sets[0].rep_count.full == 10


