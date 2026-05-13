"""Unit tests for ValidationCardBuilder."""
from __future__ import annotations

from typing import Any

import pytest


from traininglogs.agent.llm_parser import TrainingLogLLMExtract
from traininglogs.agent.validation_card_builder import ValidationCardBuilder
from traininglogs.agent.validation_card_data import UserValidationCard


def _make_extract(overrides: dict[str, Any] | None = None) -> TrainingLogLLMExtract:
    base: dict[str, Any] = {
        "date": "2026-05-12",
        "program": "Test Program",
        "phase": 2,
        "week": 3,
        "focus": "Lower",
        "session_duration_minutes": 90,
        "exercises": [
            {
                "number": 1,
                "name": "Squat",
                "exercise_type": "strength",
                "current_goal": {
                    "weight_kg": 100.0,
                    "sets": 3,
                    "rep_range": {"min": 5, "max": 8},
                    "rest": {"minutes": 3},
                },
                "warmup_sets": [
                    {"number": 1, "weight_kg": 60.0, "rep_count": 5},
                    {"number": 2, "weight_kg": 80.0, "rep_count": 3, "notes": "feel"},
                ],
                "sets": [
                    {
                        "set_type": "strength",
                        "number": 1,
                        "weight_kg": 100.0,
                        "rep_count": {"full": 6, "partial": 0},
                        "rpe": 8.0,
                        "rep_quality_assessment": "good",
                    },
                    {
                        "set_type": "strength",
                        "number": 2,
                        "weight_kg": 100.0,
                        "rep_count": {"full": 5, "partial": 1},
                        "rpe": 9.5,
                    },
                ],
                "notes": "Felt solid today",
            }
        ],
        "uncertain_fields": [],
    }
    if overrides:
        base.update(overrides)
    return TrainingLogLLMExtract.model_validate(base)


builder = ValidationCardBuilder()


class TestSessionHeader:
    def test_basic_fields(self) -> None:
        extract = _make_extract()
        card = builder.build(extract)
        h = card.session_header
        assert h.date == "2026-05-12"
        assert h.program == "Test Program"
        assert h.phase == 2
        assert h.week == 3
        assert h.focus == "Lower"
        assert h.duration_minutes == 90

    def test_no_uncertain_fields_by_default(self) -> None:
        card = builder.build(_make_extract())
        assert card.session_header.uncertain_fields == frozenset()

    def test_date_marked_uncertain(self) -> None:
        extract = _make_extract({"uncertain_fields": ["date"]})
        card = builder.build(extract)
        assert "date" in card.session_header.uncertain_fields

    def test_focus_marked_uncertain(self) -> None:
        extract = _make_extract({"uncertain_fields": ["focus"]})
        card = builder.build(extract)
        assert "focus" in card.session_header.uncertain_fields

    def test_session_duration_renamed_to_duration_minutes(self) -> None:
        extract = _make_extract({"uncertain_fields": ["session_duration_minutes"]})
        card = builder.build(extract)
        assert "duration_minutes" in card.session_header.uncertain_fields

    def test_exercise_path_does_not_bleed_to_session_header(self) -> None:
        extract = _make_extract({"uncertain_fields": ["exercises.0.sets.0.rpe"]})
        card = builder.build(extract)
        assert card.session_header.uncertain_fields == frozenset()


class TestExerciseCard:
    def test_exercise_count(self) -> None:
        card = builder.build(_make_extract())
        assert len(card.exercises) == 1

    def test_exercise_header_name_and_number(self) -> None:
        card = builder.build(_make_extract())
        h = card.exercises[0].header
        assert h.number == 1
        assert h.name == "Squat"

    def test_exercise_header_uncertain_name(self) -> None:
        extract = _make_extract({"uncertain_fields": ["exercises.0.name"]})
        card = builder.build(extract)
        assert "name" in card.exercises[0].header.uncertain_fields

    def test_exercise_path_does_not_bleed_to_different_exercise(self) -> None:
        base: dict[str, Any] = {
            "date": "2026-05-12",
            "exercises": [
                {"number": 1, "name": "Squat", "exercise_type": "strength"},
                {"number": 2, "name": "Bench", "exercise_type": "strength"},
            ],
            "uncertain_fields": ["exercises.0.name"],
        }
        extract = TrainingLogLLMExtract.model_validate(base)
        card = builder.build(extract)
        assert "name" in card.exercises[0].header.uncertain_fields
        assert "name" not in card.exercises[1].header.uncertain_fields


class TestGoalSummary:
    def test_goal_mapped_from_current_goal(self) -> None:
        card = builder.build(_make_extract())
        goal = card.exercises[0].header.goal
        assert goal is not None
        assert goal.weight_kg == 100.0
        assert goal.sets == 3
        assert goal.rep_range_min == 5
        assert goal.rep_range_max == 8
        assert goal.rest_minutes == 3
        assert goal.rest_seconds is None

    def test_no_goal_when_current_goal_absent(self) -> None:
        base: dict[str, Any] = {
            "date": "2026-05-12",
            "exercises": [{"number": 1, "name": "Plank", "exercise_type": "strength"}],
        }
        extract = TrainingLogLLMExtract.model_validate(base)
        card = builder.build(extract)
        assert card.exercises[0].header.goal is None


class TestWarmupRows:
    def test_warmup_row_count(self) -> None:
        card = builder.build(_make_extract())
        assert len(card.exercises[0].warmup_rows) == 2

    def test_warmup_row_fields(self) -> None:
        card = builder.build(_make_extract())
        row = card.exercises[0].warmup_rows[0]
        assert row.number == 1
        assert row.weight_kg == 60.0
        assert row.rep_count == 5
        assert row.notes is None

    def test_warmup_row_with_notes(self) -> None:
        card = builder.build(_make_extract())
        row = card.exercises[0].warmup_rows[1]
        assert row.notes == "feel"

    def test_warmup_uncertain_field_routed(self) -> None:
        extract = _make_extract({"uncertain_fields": ["exercises.0.warmup_sets.0.weight_kg"]})
        card = builder.build(extract)
        assert "weight_kg" in card.exercises[0].warmup_rows[0].uncertain_fields
        assert "weight_kg" not in card.exercises[0].warmup_rows[1].uncertain_fields


class TestWorkingSetRows:
    def test_working_set_count(self) -> None:
        card = builder.build(_make_extract())
        assert len(card.exercises[0].working_set_rows) == 2

    def test_strength_set_fields(self) -> None:
        card = builder.build(_make_extract())
        row = card.exercises[0].working_set_rows[0]
        assert row.number == 1
        assert row.weight_kg == 100.0
        assert row.reps == "6"
        assert row.rpe == 8.0
        assert row.quality == "good"

    def test_partial_reps_formatted(self) -> None:
        card = builder.build(_make_extract())
        row = card.exercises[0].working_set_rows[1]
        assert row.reps == "5+1"

    def test_working_set_uncertain_field_routed(self) -> None:
        extract = _make_extract({"uncertain_fields": ["exercises.0.sets.1.rpe"]})
        card = builder.build(extract)
        assert "rpe" in card.exercises[0].working_set_rows[1].uncertain_fields
        assert "rpe" not in card.exercises[0].working_set_rows[0].uncertain_fields

    def test_activity_set_fields(self) -> None:
        base: dict[str, Any] = {
            "date": "2026-05-12",
            "exercises": [
                {
                    "number": 1,
                    "name": "Row",
                    "exercise_type": "activity",
                    "sets": [
                        {
                            "set_type": "activity",
                            "number": 1,
                            "duration_seconds": 1800,
                            "distance_meters": 5000.0,
                            "heart_rate_bpm": 150,
                        }
                    ],
                }
            ],
        }
        extract = TrainingLogLLMExtract.model_validate(base)
        card = builder.build(extract)
        row = card.exercises[0].working_set_rows[0]
        assert row.duration_seconds == 1800
        assert row.distance_meters == 5000.0
        assert row.heart_rate_bpm == 150
        assert row.weight_kg is None
        assert row.reps is None


class TestRepsFormatting:
    def _row_for_set(self, set_data: dict[str, Any]) -> Any:
        base: dict[str, Any] = {
            "date": "2026-05-12",
            "exercises": [
                {"number": 1, "name": "X", "exercise_type": "strength", "sets": [set_data]}
            ],
        }
        extract = TrainingLogLLMExtract.model_validate(base)
        card = builder.build(extract)
        return card.exercises[0].working_set_rows[0]

    def test_simple_reps(self) -> None:
        row = self._row_for_set(
            {"set_type": "strength", "number": 1, "weight_kg": 80.0, "rep_count": {"full": 8, "partial": 0}}
        )
        assert row.reps == "8"

    def test_partial_reps(self) -> None:
        row = self._row_for_set(
            {"set_type": "strength", "number": 1, "weight_kg": 80.0, "rep_count": {"full": 8, "partial": 2}}
        )
        assert row.reps == "8+2"

    def test_unilateral_reps(self) -> None:
        row = self._row_for_set(
            {
                "set_type": "strength",
                "number": 1,
                "unilateral_rep_count": {
                    "left": {"full": 10, "partial": 0},
                    "right": {"full": 9, "partial": 1},
                },
            }
        )
        assert row.reps == "10L / 9+1R"

    def test_no_reps_when_neither_set(self) -> None:
        row = self._row_for_set({"set_type": "strength", "number": 1, "weight_kg": 80.0})
        assert row.reps is None


class TestFailureTechnique:
    def _row_with_failure(self, technique: dict[str, Any]) -> Any:
        base: dict[str, Any] = {
            "date": "2026-05-12",
            "exercises": [
                {
                    "number": 1,
                    "name": "X",
                    "exercise_type": "strength",
                    "sets": [
                        {
                            "set_type": "strength",
                            "number": 1,
                            "weight_kg": 80.0,
                            "rep_count": {"full": 8},
                            "rpe": 10.0,
                            "failure_technique": technique,
                        }
                    ],
                }
            ],
        }
        extract = TrainingLogLLMExtract.model_validate(base)
        card = builder.build(extract)
        return card.exercises[0].working_set_rows[0]

    def test_llp(self) -> None:
        row = self._row_with_failure({"technique_type": "LLP", "details": {"partial_rep_count": 5}})
        assert row.failure_technique == "LLP (5 partials)"

    def test_static_hold(self) -> None:
        row = self._row_with_failure({"technique_type": "StaticHold", "details": {"hold_duration_seconds": 10}})
        assert row.failure_technique == "Static Hold (10s)"

    def test_myo_reps(self) -> None:
        row = self._row_with_failure({
            "technique_type": "MyoReps",
            "details": {"mini_sets": [{"number": 1, "rep_count": {"full": 5}}, {"number": 2, "rep_count": {"full": 4}}]},
        })
        assert row.failure_technique == "Myo-reps (2 mini-sets)"

    def test_drop_set(self) -> None:
        row = self._row_with_failure({
            "technique_type": "DropSet",
            "details": {"drop_sets": [
                {"number": 1, "weight_kg": 70.0, "rep_count": {"full": 8}},
                {"number": 2, "weight_kg": 60.0, "rep_count": {"full": 8}},
            ]},
        })
        assert row.failure_technique == "Drop set (2 drops)"


class TestNotePreview:
    def test_note_preview_set(self) -> None:
        card = builder.build(_make_extract())
        assert card.exercises[0].note_preview is not None
        assert "Felt solid" in card.exercises[0].note_preview.display

    def test_no_note_when_absent(self) -> None:
        base: dict[str, Any] = {
            "date": "2026-05-12",
            "exercises": [{"number": 1, "name": "X", "exercise_type": "strength"}],
        }
        extract = TrainingLogLLMExtract.model_validate(base)
        card = builder.build(extract)
        assert card.exercises[0].note_preview is None

    def test_warmup_note_preview(self) -> None:
        base: dict[str, Any] = {
            "date": "2026-05-12",
            "exercises": [
                {
                    "number": 1,
                    "name": "X",
                    "exercise_type": "strength",
                    "warmup_notes": "Felt tight in hips",
                }
            ],
        }
        extract = TrainingLogLLMExtract.model_validate(base)
        card = builder.build(extract)
        assert card.exercises[0].warmup_note_preview is not None
