"""Unit tests for extract_exercise_labels() — the narrow-path worker call added by the
extraction-accuracy fix (see extraction-accuracy-plan.md Step 2), used when
parse_exercise_block() already supplied an exercise's numeric spine deterministically. Mirrors
tests/test_agent_extraction.py's TestExtractExercise pattern for the full-extraction path.
Fake providers only, no real LLM calls."""
from __future__ import annotations

from typing import Any

import pytest

from traininglogs.agent.extraction import LABELS_TOOL_NAME, extract_exercise_labels
from traininglogs.agent.prompts import LABELS_SYSTEM_PROMPT
from traininglogs.agent.schemas import LLMParserError


class CapturingProvider:
    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw = raw
        self.calls: list[tuple[str, dict, str, str, str]] = []

    def extract(
        self, text: str, tool_schema: dict, system_prompt: str, tool_name: str, tool_description: str
    ) -> dict:
        self.calls.append((text, tool_schema, system_prompt, tool_name, tool_description))
        return self._raw


class AlwaysFailProvider:
    def extract(
        self, text: str, tool_schema: dict, system_prompt: str, tool_name: str, tool_description: str
    ) -> dict:
        raise LLMParserError("provider always fails")


VALID_LABELS_RAW: dict[str, Any] = {
    "name": "Incline DB Press",
    "tags": ["muscle_growth"],
    "modality": "dumbbell",
    "movement_pattern": ["push"],
    "uncertain_fields": [],
}


class TestExtractExerciseLabels:
    def test_happy_path(self) -> None:
        result = extract_exercise_labels(
            "some workout text", 2, [1, 2, 3], provider=CapturingProvider(VALID_LABELS_RAW)
        )
        assert result.name == "Incline DB Press"
        assert result.tags == ["muscle_growth"]
        assert result.uncertain_fields == []

    def test_provider_receives_position_set_numbers_and_labels_prompt_and_tool(self) -> None:
        provider = CapturingProvider(VALID_LABELS_RAW)
        extract_exercise_labels("the isolated chunk", 3, [1, 2, 3], provider=provider)
        text, tool_schema, system_prompt, tool_name, tool_description = provider.calls[0]
        assert "3" in text
        assert "1, 2, 3" in text
        assert "the isolated chunk" in text
        assert system_prompt == LABELS_SYSTEM_PROMPT
        assert tool_name == LABELS_TOOL_NAME
        # No sets/warmup_sets fields at all — the whole point of this narrow schema.
        assert "sets" not in tool_schema["properties"]
        assert "warmup_sets" not in tool_schema["properties"]

    def test_invalid_raw_raises_llm_parser_error(self) -> None:
        bad_raw = {"name": ""}
        with pytest.raises(LLMParserError):
            extract_exercise_labels("text", 1, [1], provider=CapturingProvider(bad_raw))

    def test_provider_error_propagates(self) -> None:
        with pytest.raises(LLMParserError):
            extract_exercise_labels("text", 1, [1], provider=AlwaysFailProvider())

    def test_set_notes_and_exercise_rpe_target_set_round_trip(self) -> None:
        raw = dict(VALID_LABELS_RAW, set_notes={"3": "grip slipped"}, exercise_rpe_target_set=3)
        result = extract_exercise_labels("text", 1, [1, 2, 3], provider=CapturingProvider(raw))
        assert result.set_notes == {"3": "grip slipped"}
        assert result.exercise_rpe_target_set == 3
