"""Corrections as patches. No real LLM calls — stub providers only.

The behaviour under test changed on 2026-08-09. The model used to be sent the whole extract and
asked for the whole extract back, with "keep all unchanged fields exactly as they are" in the
prompt as the only guarantee. Now it returns the fields it is changing and Python applies them,
which turns that sentence into a property of the code.
"""
from __future__ import annotations

from typing import Any

import pytest

from traininglogs.agent.llm_extract_validator import (
    CORRECTION_TOOL_NAME,
    LLMExtractValidator,
)
from traininglogs.agent.prompts import CORRECTION_SYSTEM_PROMPT
from traininglogs.agent.schemas import LLMParserError, TrainingLogLLMExtract

_VALID_RAW: dict[str, Any] = {
    "date": "2026-05-12",
    "focus": "Upper",
    "exercises": [
        {
            "number": 1,
            "name": "Bench Press",
            "notes": "felt strong",
            "sets": [
                {"number": 1, "weight_kg": 80.0, "rep_count": {"full": 8, "partial": 0}, "rpe": 8.0},
                {"number": 2, "weight_kg": 80.0, "rep_count": {"full": 6, "partial": 0}, "rpe": 9.0},
            ],
        },
        {
            "number": 2,
            "name": "Overhead Press",
            "sets": [
                {"number": 1, "weight_kg": 40.0, "rep_count": {"full": 10, "partial": 0}}
            ],
        },
    ],
    "uncertain_fields": ["exercises.0.sets.1.rpe"],
}


class StubProvider:
    """Returns a fixed patch on every extract() call."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw = raw
        self.calls: list[tuple[str, dict, str, str]] = []

    def extract(
        self, text: str, tool_schema: dict, system_prompt: str, tool_name: str,
        tool_description: str, validate=None
    ) -> dict:
        self.calls.append((text, tool_schema, system_prompt, tool_name))
        return self._raw


class FailingProvider:
    def extract(
        self, text: str, tool_schema: dict, system_prompt: str, tool_name: str,
        tool_description: str, validate=None
    ) -> dict:
        raise LLMParserError("provider always fails")


def make_extract() -> TrainingLogLLMExtract:
    return TrainingLogLLMExtract.model_validate(_VALID_RAW)


class TestCorrectionsApplyOnlyWhatTheyName:
    def test_a_named_field_changes(self) -> None:
        provider = StubProvider({"edits": [{"path": "exercises.0.sets.1.rpe", "value": 10.0}]})
        updated, edits = LLMExtractValidator(provider).apply_correction(
            make_extract(), "the second bench set was RPE 10"
        )

        assert updated.exercises[0].sets[1].rpe == 10.0
        assert [e.path for e in edits] == ["exercises.0.sets.1.rpe"]

    def test_everything_else_is_untouched(self) -> None:
        """The guarantee that used to be a sentence in a prompt. Python copies the original and
        sets only the named paths, so an unnamed field cannot change."""
        before = make_extract()
        provider = StubProvider({"edits": [{"path": "exercises.0.sets.1.rpe", "value": 10.0}]})
        after, _ = LLMExtractValidator(provider).apply_correction(before, "fix the rpe")

        assert after.exercises[0].sets[0] == before.exercises[0].sets[0]
        assert after.exercises[1] == before.exercises[1]
        assert after.exercises[0].name == "Bench Press"
        assert after.exercises[0].notes == "felt strong"
        assert after.date == before.date

    def test_a_field_can_be_cleared_with_null(self) -> None:
        provider = StubProvider({"edits": [{"path": "exercises.0.notes", "value": None}]})
        updated, _ = LLMExtractValidator(provider).apply_correction(
            make_extract(), "drop that note"
        )
        assert updated.exercises[0].notes is None

    def test_a_whole_list_can_be_replaced_to_change_its_length(self) -> None:
        """How a missed set gets added, or one that never happened gets removed."""
        provider = StubProvider({
            "edits": [{
                "path": "exercises.1.sets",
                "value": [
                    {"number": 1, "weight_kg": 40.0, "rep_count": {"full": 10, "partial": 0}},
                    {"number": 2, "weight_kg": 40.0, "rep_count": {"full": 8, "partial": 0}},
                ],
            }]
        })
        updated, _ = LLMExtractValidator(provider).apply_correction(
            make_extract(), "I did a second set of overhead press, 40 x 8"
        )
        assert len(updated.exercises[1].sets) == 2
        assert updated.exercises[1].sets[1].rep_count.full == 8

    def test_no_edits_leaves_the_extract_alone(self) -> None:
        before = make_extract()
        provider = StubProvider({"edits": []})
        after, edits = LLMExtractValidator(provider).apply_correction(before, "looks fine actually")

        assert edits == []
        assert after == before

    def test_uncertain_fields_survive_a_correction(self) -> None:
        provider = StubProvider({"edits": [{"path": "focus", "value": "Upper Strength"}]})
        updated, _ = LLMExtractValidator(provider).apply_correction(make_extract(), "upper strength")
        assert updated.uncertain_fields == ["exercises.0.sets.1.rpe"]


class TestWhatTheProviderIsAsked:
    def test_it_is_asked_for_a_patch_not_a_workout(self) -> None:
        provider = StubProvider({"edits": []})
        LLMExtractValidator(provider).apply_correction(make_extract(), "x")
        _, tool_schema, system_prompt, tool_name = provider.calls[0]

        assert tool_name == CORRECTION_TOOL_NAME
        assert system_prompt == CORRECTION_SYSTEM_PROMPT
        assert "edits" in tool_schema["properties"]
        assert "exercises" not in tool_schema["properties"], (
            "asking for the whole workout back is the shape this replaced"
        )

    def test_the_prompt_carries_the_extract_and_the_correction(self) -> None:
        provider = StubProvider({"edits": []})
        LLMExtractValidator(provider).apply_correction(make_extract(), "the rpe was 10")
        text = provider.calls[0][0]

        assert "the rpe was 10" in text
        assert "Bench Press" in text

    def test_called_once_per_correction(self) -> None:
        provider = StubProvider({"edits": []})
        LLMExtractValidator(provider).apply_correction(make_extract(), "x")
        assert len(provider.calls) == 1


class TestBadPatchesAreRefusedNotAbsorbed:
    def test_a_path_that_does_not_exist_raises(self) -> None:
        """A typo'd path silently changing nothing is worse than a failure — the person would
        believe their correction landed."""
        provider = StubProvider({"edits": [{"path": "exercises.0.rpe", "value": 9.0}]})
        with pytest.raises(LLMParserError, match="could not be applied"):
            LLMExtractValidator(provider).apply_correction(make_extract(), "x")

    def test_a_list_position_out_of_range_raises(self) -> None:
        provider = StubProvider({"edits": [{"path": "exercises.5.name", "value": "Squat"}]})
        with pytest.raises(LLMParserError, match="out of range"):
            LLMExtractValidator(provider).apply_correction(make_extract(), "x")

    def test_an_edit_that_breaks_the_schema_raises(self) -> None:
        provider = StubProvider({"edits": [{"path": "date", "value": "not-a-date"}]})
        with pytest.raises(LLMParserError, match="failed validation"):
            LLMExtractValidator(provider).apply_correction(make_extract(), "x")

    def test_a_malformed_patch_raises(self) -> None:
        provider = StubProvider({"edits": [{"value": 9.0}]})   # no path
        with pytest.raises(LLMParserError, match="not a usable patch"):
            LLMExtractValidator(provider).apply_correction(make_extract(), "x")

    def test_provider_failure_propagates(self) -> None:
        with pytest.raises(LLMParserError):
            LLMExtractValidator(FailingProvider()).apply_correction(make_extract(), "x")
