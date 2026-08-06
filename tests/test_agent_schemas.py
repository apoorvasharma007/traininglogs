"""Unit tests for the split-extraction schemas: SessionShellExtract, ExerciseExtract,
ExercisePosition, ExerciseSplit. TrainingLogLLMExtract (the monolithic extract model) is
covered separately in test_agent_llm_parser.py."""
from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from traininglogs.agent.schemas import (
    ExerciseExtract,
    ExercisePosition,
    ExerciseSplit,
    SessionShellExtract,
)


class TestSessionShellExtract:
    def test_valid_construction(self) -> None:
        shell = SessionShellExtract(
            date="2026-05-12",
            program="Test Program",
            phase=3,
            week=11,
            focus="Lower Strength",
            session_duration_minutes=150,
        )
        assert shell.date == "2026-05-12"
        assert shell.program == "Test Program"
        assert shell.uncertain_fields == []

    def test_optional_fields_default_none(self) -> None:
        shell = SessionShellExtract(date="2026-05-12")
        assert shell.program is None
        assert shell.phase is None
        assert shell.week is None
        assert shell.is_deload_week is None
        assert shell.focus is None
        assert shell.session_duration_minutes is None
        assert shell.warmup is None
        assert shell.cooldown is None
        assert shell.notes is None

    def test_invalid_date_raises(self) -> None:
        with pytest.raises(ValidationError):
            SessionShellExtract(date="not-a-date")

    def test_uncertain_fields_populated(self) -> None:
        shell = SessionShellExtract(date="2026-05-12", uncertain_fields=["phase"])
        assert "phase" in shell.uncertain_fields

    def test_has_no_exercises_field(self) -> None:
        assert "exercises" not in SessionShellExtract.model_fields

    def test_json_round_trip(self) -> None:
        shell = SessionShellExtract(date="2026-05-12", focus="Upper", notes="felt good")
        dumped = shell.model_dump(mode="json")
        restored = SessionShellExtract.model_validate(dumped)
        assert restored == shell


class TestExerciseExtract:
    _VALID_EXERCISE: dict[str, Any] = {
        "name": "Bench Press",
        "sets": [
            {
                "number": 1,
                "source_line": "1. 80kg x 8 RPE 8",
                "weight_kg": 80.0,
                "reps": "8",
                "rpe": 8.0,
            }
        ],
    }

    def test_valid_construction(self) -> None:
        extract = ExerciseExtract(**self._VALID_EXERCISE)
        assert extract.name == "Bench Press"
        assert extract.uncertain_fields == []

    def test_uncertain_fields_populated(self) -> None:
        extract = ExerciseExtract(**self._VALID_EXERCISE, uncertain_fields=["sets.0.rpe"])
        assert "sets.0.rpe" in extract.uncertain_fields

    def test_invalid_exercise_field_raises(self) -> None:
        bad = dict(self._VALID_EXERCISE, name="   ")
        with pytest.raises(ValidationError):
            ExerciseExtract(**bad)

    def test_an_exercise_with_no_sets_at_all_is_rejected(self) -> None:
        """A schema-valid but empty result is a non-answer. Rejecting it here is what routes it
        into the provider's retry instead of letting a session look clean with its sets gone."""
        with pytest.raises(ValidationError, match="no working sets and no warmup sets"):
            ExerciseExtract(name="Bench Press")

    def test_json_round_trip(self) -> None:
        extract = ExerciseExtract(**self._VALID_EXERCISE, uncertain_fields=["sets.0.rpe"])
        dumped = extract.model_dump(mode="json")
        restored = ExerciseExtract.model_validate(dumped)
        assert restored == extract

    def test_schema_is_flat_not_nested(self) -> None:
        """Regression guard for the live-testing finding: tool-calling models flatten a
        single-nested-object schema regardless of prompt wording, so ExerciseExtract must
        expose Exercise's fields directly rather than under an "exercise" wrapper key."""
        schema = ExerciseExtract.model_json_schema()
        assert "name" in schema["properties"]
        assert "sets" in schema["properties"]
        assert "exercise" not in schema["properties"]


class TestExercisePosition:
    def test_valid_construction(self) -> None:
        entry = ExercisePosition(position=1, name="Bench Press", anchor="Bench Press")
        assert entry.position == 1
        assert entry.name == "Bench Press"
        assert entry.anchor == "Bench Press"

    def test_position_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            ExercisePosition(position=0, name="Bench Press", anchor="Bench Press")

    def test_position_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            ExercisePosition(position=-1, name="Bench Press", anchor="Bench Press")

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            ExercisePosition(position=1, name="", anchor="Bench Press")

    def test_whitespace_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            ExercisePosition(position=1, name="   ", anchor="Bench Press")

    def test_empty_anchor_raises(self) -> None:
        with pytest.raises(ValidationError):
            ExercisePosition(position=1, name="Bench Press", anchor="")

    def test_whitespace_anchor_raises(self) -> None:
        with pytest.raises(ValidationError):
            ExercisePosition(position=1, name="Bench Press", anchor="   ")

    def test_json_round_trip(self) -> None:
        entry = ExercisePosition(position=2, name="Squat", anchor="Squat 4x8")
        dumped = entry.model_dump(mode="json")
        restored = ExercisePosition.model_validate(dumped)
        assert restored == entry


class TestExerciseSplit:
    def test_valid_construction(self) -> None:
        split = ExerciseSplit(
            exercises=[
                ExercisePosition(position=1, name="Bench Press", anchor="Bench Press"),
                ExercisePosition(position=2, name="Overhead Press", anchor="Overhead Press"),
            ]
        )
        assert len(split.exercises) == 2
        assert split.exercises[0].name == "Bench Press"

    def test_empty_list_accepted(self) -> None:
        split = ExerciseSplit(exercises=[])
        assert split.exercises == []

    def test_invalid_entry_raises(self) -> None:
        with pytest.raises(ValidationError):
            ExerciseSplit(exercises=[{"position": 0, "name": "Bench Press", "anchor": "Bench Press"}])

    def test_json_round_trip(self) -> None:
        split = ExerciseSplit(
            exercises=[
                ExercisePosition(position=1, name="Bench Press", anchor="Bench Press"),
                ExercisePosition(position=2, name="Overhead Press", anchor="Overhead Press"),
            ]
        )
        dumped = split.model_dump(mode="json")
        restored = ExerciseSplit.model_validate(dumped)
        assert restored == split


_SET = {"number": 1, "source_line": "1. 80kg x 8", "weight_kg": 80.0, "reps": "8"}


class TestNullUncertainFieldsIsAccepted:
    """Models serialise "nothing uncertain" as null, and a schema that only accepts an array
    gets the whole tool call rejected for it. On 2026-08-06 that cost two complete, correct
    extractions out of 22 exercises -- Groq returned `"uncertain_fields": null` and its
    server-side validator refused the call before we ever saw the answer."""

    def test_the_schema_permits_null(self) -> None:
        import json

        from traininglogs.agent.schemas import ExerciseExtract, SessionShellExtract

        for model in (ExerciseExtract, SessionShellExtract):
            prop = model.model_json_schema()["properties"]["uncertain_fields"]
            assert "null" in json.dumps(prop), f"{model.__name__} would reject null"

    def test_null_becomes_an_empty_list(self) -> None:
        from traininglogs.agent.schemas import ExerciseExtract

        assert ExerciseExtract(
            name="Bench", sets=[_SET], uncertain_fields=None
        ).uncertain_fields == []

    def test_omitted_is_still_an_empty_list(self) -> None:
        from traininglogs.agent.schemas import ExerciseExtract

        assert ExerciseExtract(name="Bench", sets=[_SET]).uncertain_fields == []
