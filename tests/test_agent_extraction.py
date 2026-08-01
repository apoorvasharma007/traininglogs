"""Unit tests for the three small-call functions added by the orchestration refactor:
segment(), extract_shell(), extract_exercise(). Each is tested against a fake provider —
no real LLM calls. parse() (the monolithic path) is covered separately in
test_agent_llm_parser.py."""
from __future__ import annotations

from typing import Any

import pytest

from traininglogs.agent.extraction import (
    SEGMENT_TOOL_NAME,
    SHELL_TOOL_NAME,
    WORKER_TOOL_NAME,
    extract_exercise,
    extract_shell,
    segment,
)
from traininglogs.agent.prompts import SHELL_SYSTEM_PROMPT, SPLITTER_SYSTEM_PROMPT, WORKER_SYSTEM_PROMPT
from traininglogs.agent.schemas import LLMParserError


class CapturingProvider:
    """Returns a fixed dict on every call; records every call's arguments."""

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


VALID_SPLIT_RAW: dict[str, Any] = {
    "exercises": [
        {"position": 1, "name": "Bench Press"},
        {"position": 2, "name": "Overhead Press"},
    ]
}

VALID_SHELL_RAW: dict[str, Any] = {
    "date": "2026-05-12",
    "focus": "Upper Strength",
    "session_duration_minutes": 90,
}

VALID_EXERCISE_EXTRACT_RAW: dict[str, Any] = {
    "exercise": {
        "number": 2,
        "name": "Overhead Press",
        "sets": [
            {"number": 1, "weight_kg": 40.0, "rep_count": {"full": 8, "partial": 0}},
        ],
    },
    "uncertain_fields": [],
}


class TestSegment:
    def test_happy_path(self) -> None:
        split = segment("some workout text", provider=CapturingProvider(VALID_SPLIT_RAW))
        assert [e.name for e in split.exercises] == ["Bench Press", "Overhead Press"]
        assert [e.position for e in split.exercises] == [1, 2]

    def test_provider_receives_splitter_prompt_and_tool(self) -> None:
        provider = CapturingProvider(VALID_SPLIT_RAW)
        segment("my workout", provider=provider)
        text, tool_schema, system_prompt, tool_name, tool_description = provider.calls[0]
        assert text == "my workout"
        assert system_prompt == SPLITTER_SYSTEM_PROMPT
        assert tool_name == SEGMENT_TOOL_NAME
        assert "exercises" in str(tool_schema)

    def test_invalid_raw_raises_llm_parser_error(self) -> None:
        bad_raw = {"exercises": [{"position": 0, "name": "Bench Press"}]}
        with pytest.raises(LLMParserError):
            segment("text", provider=CapturingProvider(bad_raw))

    def test_provider_error_propagates(self) -> None:
        with pytest.raises(LLMParserError):
            segment("text", provider=AlwaysFailProvider())


class TestExtractShell:
    def test_happy_path(self) -> None:
        shell = extract_shell("some workout text", provider=CapturingProvider(VALID_SHELL_RAW))
        assert shell.date == "2026-05-12"
        assert shell.focus == "Upper Strength"

    def test_provider_receives_shell_prompt_and_tool(self) -> None:
        provider = CapturingProvider(VALID_SHELL_RAW)
        extract_shell("my workout", provider=provider)
        text, tool_schema, system_prompt, tool_name, tool_description = provider.calls[0]
        assert text == "my workout"
        assert system_prompt == SHELL_SYSTEM_PROMPT
        assert tool_name == SHELL_TOOL_NAME
        assert "exercises" not in tool_schema["properties"]

    def test_invalid_raw_raises_llm_parser_error(self) -> None:
        with pytest.raises(LLMParserError):
            extract_shell("text", provider=CapturingProvider({"date": "not-a-date"}))

    def test_provider_error_propagates(self) -> None:
        with pytest.raises(LLMParserError):
            extract_shell("text", provider=AlwaysFailProvider())


class TestExtractExercise:
    def test_happy_path(self) -> None:
        result = extract_exercise(
            "some workout text", 2, provider=CapturingProvider(VALID_EXERCISE_EXTRACT_RAW)
        )
        assert result.exercise.number == 2
        assert result.exercise.name == "Overhead Press"
        assert result.uncertain_fields == []

    def test_provider_receives_position_and_full_text(self) -> None:
        provider = CapturingProvider(VALID_EXERCISE_EXTRACT_RAW)
        extract_exercise("the full session note", 3, provider=provider)
        text, tool_schema, system_prompt, tool_name, tool_description = provider.calls[0]
        assert "3" in text
        assert "the full session note" in text
        assert system_prompt == WORKER_SYSTEM_PROMPT
        assert tool_name == WORKER_TOOL_NAME

    def test_invalid_raw_raises_llm_parser_error(self) -> None:
        bad_raw = {"exercise": {"number": 0, "name": "Overhead Press"}}
        with pytest.raises(LLMParserError):
            extract_exercise("text", 1, provider=CapturingProvider(bad_raw))

    def test_provider_error_propagates(self) -> None:
        with pytest.raises(LLMParserError):
            extract_exercise("text", 1, provider=AlwaysFailProvider())

    def test_self_contained_no_call_ordering_dependency(self) -> None:
        """Decision 7: a worker is `text (+ position) -> one Exercise` with no dependence on
        segment()/extract_shell() having run first, or on any other worker's result. Calling
        it standalone, out of order, for a position other than 1 must work identically."""
        result = extract_exercise(
            "some workout text", 2, provider=CapturingProvider(VALID_EXERCISE_EXTRACT_RAW)
        )
        assert result.exercise.number == 2
