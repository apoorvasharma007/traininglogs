"""
LLM parser unit tests. The AnthropicProvider is never instantiated here —
all tests inject a stub ExtractionProvider so no API calls are made.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from traininglogs.agent.extraction import parse
from traininglogs.agent.prompts import SYSTEM_PROMPT
from traininglogs.agent.schemas import LLMParserError, TrainingLogLLMExtract
from traininglogs.models.models import Exercise, RepCount, WorkingSet


# --- stub providers ---

class StubProvider:
    """Returns a fixed dict on every call."""

    def __init__(self, raw: dict) -> None:
        self._raw = raw

    def extract(
        self, text: str, tool_schema: dict, system_prompt: str, tool_name: str, tool_description: str
    ) -> dict:
        return self._raw


class FailThenSucceedProvider:
    """Raises LLMParserError on the first N calls, then returns a valid dict."""

    def __init__(self, raw: dict, fail_times: int = 1) -> None:
        self._raw = raw
        self._fail_times = fail_times
        self._calls = 0

    def extract(
        self, text: str, tool_schema: dict, system_prompt: str, tool_name: str, tool_description: str
    ) -> dict:
        self._calls += 1
        if self._calls <= self._fail_times:
            raise LLMParserError("simulated provider failure")
        return self._raw


class AlwaysFailProvider:
    def extract(
        self, text: str, tool_schema: dict, system_prompt: str, tool_name: str, tool_description: str
    ) -> dict:
        raise LLMParserError("always fails")


# --- fixtures ---

VALID_STRENGTH_RAW: dict[str, Any] = {
    "date": "2026-05-12",
    "program": "Test Program",
    "phase": 3,
    "week": 11,
    "focus": "Lower Strength",
    "session_duration_minutes": 150,
    "exercises": [
        {
            "number": 1,
            "name": "Seated Leg Hamstring Curl",
            "tags": ["muscle_growth"],
            "modality": "machine",
            "movement_pattern": ["hip_hinge"],
            "current_goal": {
                "weight_kg": 63.0,
                "sets": 3,
                "rep_range": {"min": 10, "max": 12},
                "rest": {"minutes": 2},
            },
            "warmup_sets": [
                {"number": 1, "weight_kg": 29.0, "notes": "feel"},
                {"number": 2, "weight_kg": 57.0, "notes": "feel"},
            ],
            "sets": [
                {
                    "number": 1,
                    "weight_kg": 63.0,
                    "rep_count": {"full": 12, "partial": 0},
                    "rpe": 10.0,
                    "rep_quality_assessment": "good",
                },
                {
                    "number": 2,
                    "weight_kg": 63.0,
                    "rep_count": {"full": 12, "partial": 0},
                    "rpe": 10.0,
                    "rep_quality_assessment": "good",
                },
                {
                    "number": 3,
                    "weight_kg": 63.0,
                    "rep_count": {"full": 11, "partial": 0},
                    "rpe": 10.0,
                    "rep_quality_assessment": "good",
                    "failure_technique": {
                        "technique_type": "LLP",
                        "details": {"partial_rep_count": 10},
                    },
                },
            ],
        }
    ],
    "uncertain_fields": [],
}


# --- TrainingLogLLMExtract model ---

class TestTrainingLogLLMExtract:
    def test_valid_construction(self) -> None:
        extract = TrainingLogLLMExtract.model_validate(VALID_STRENGTH_RAW)
        assert extract.date == "2026-05-12"
        assert extract.program == "Test Program"
        assert len(extract.exercises) == 1
        assert extract.uncertain_fields == []

    def test_uncertain_fields_populated(self) -> None:
        raw = dict(VALID_STRENGTH_RAW)
        raw["uncertain_fields"] = ["exercises.0.sets.1.rpe"]
        extract = TrainingLogLLMExtract.model_validate(raw)
        assert "exercises.0.sets.1.rpe" in extract.uncertain_fields

    def test_optional_fields_default_none(self) -> None:
        minimal = {
            "date": "2026-05-12",
            "exercises": [{"number": 1, "name": "Plank"}],
        }
        extract = TrainingLogLLMExtract.model_validate(minimal)
        assert extract.program is None
        assert extract.phase is None
        assert extract.week is None
        assert extract.is_deload_week is None
        assert extract.focus is None
        assert extract.session_duration_minutes is None
        assert extract.warmup is None
        assert extract.cooldown is None
        assert extract.notes is None

    def test_notes_accepted(self) -> None:
        raw = dict(VALID_STRENGTH_RAW, notes="Legs are sore, warmup ran long.")
        extract = TrainingLogLLMExtract.model_validate(raw)
        assert extract.notes == "Legs are sore, warmup ran long."

    def test_invalid_date_raises(self) -> None:
        raw = dict(VALID_STRENGTH_RAW, date="not-a-date")
        with pytest.raises(ValidationError):
            TrainingLogLLMExtract.model_validate(raw)

    def test_exercises_validated_by_existing_model(self) -> None:
        raw = dict(VALID_STRENGTH_RAW)
        raw["exercises"] = [{"number": 0, "name": "Squat"}]  # number=0 is invalid
        with pytest.raises(ValidationError):
            TrainingLogLLMExtract.model_validate(raw)

    def test_model_json_schema_contains_exercise_defs(self) -> None:
        schema = TrainingLogLLMExtract.model_json_schema()
        schema_str = str(schema)
        assert "exercises" in schema_str
        assert "date" in schema_str

    def test_cardio_set_accepted(self) -> None:
        raw = {
            "date": "2026-05-12",
            "exercises": [
                {
                    "number": 1,
                    "name": "Row",
                    "tags": ["cardiorespiratory"],
                    "modality": "machine",
                    "sets": [
                        {
                            "number": 1,
                            "duration_seconds": 1800,
                            "distance_meters": 5000.0,
                            "heart_rate_bpm": 155,
                        }
                    ],
                }
            ],
        }
        extract = TrainingLogLLMExtract.model_validate(raw)
        s = extract.exercises[0].sets[0]
        assert s.duration_seconds == 1800
        assert s.distance_meters == 5000.0
        assert s.heart_rate_bpm == 155


# --- parse() ---

class TestParse:
    def test_happy_path(self) -> None:
        extract = parse("some workout text", provider=StubProvider(VALID_STRENGTH_RAW))
        assert extract.date == "2026-05-12"
        assert len(extract.exercises) == 1

    def test_provider_receives_text_and_schema(self) -> None:
        calls: list[tuple[str, dict]] = []

        class CapturingProvider:
            def extract(
                self, text: str, tool_schema: dict, system_prompt: str, tool_name: str, tool_description: str
            ) -> dict:
                calls.append((text, tool_schema))
                return VALID_STRENGTH_RAW

        parse("my workout", provider=CapturingProvider())
        assert len(calls) == 1
        assert calls[0][0] == "my workout"
        assert isinstance(calls[0][1], dict)
        assert "exercises" in str(calls[0][1])

    def test_provider_error_raises_llm_parser_error(self) -> None:
        with pytest.raises(LLMParserError):
            parse("text", provider=AlwaysFailProvider())

    def test_invalid_raw_dict_raises_llm_parser_error(self) -> None:
        bad_raw = {"date": "2026-05-12", "exercises": [{"number": 0, "name": "Squat"}]}
        with pytest.raises(LLMParserError):
            parse("text", provider=StubProvider(bad_raw))

    def test_uncertain_fields_preserved(self) -> None:
        raw = dict(VALID_STRENGTH_RAW, uncertain_fields=["exercises.0.sets.0.rpe"])
        extract = parse("text", provider=StubProvider(raw))
        assert "exercises.0.sets.0.rpe" in extract.uncertain_fields

    def test_default_provider_is_anthropic(self) -> None:
        # Just verify AnthropicProvider is used when none supplied.
        # Don't call .extract() — just check the type.
        with patch("traininglogs.agent.extraction.AnthropicProvider") as mock_cls:
            mock_provider = MagicMock()
            mock_provider.extract.return_value = VALID_STRENGTH_RAW
            mock_cls.return_value = mock_provider
            result = parse("text")
            mock_cls.assert_called_once()
            assert result.date == "2026-05-12"


class TestProviderTemperature:
    """Extraction must be deterministic — the same input text should produce the same
    fields every time. A non-zero sampling temperature is why the same free-prose file
    extracted differently across repeated live Groq calls (some runs silently lost
    exercise-level remarks that other runs correctly captured)."""

    def test_anthropic_provider_pins_temperature_zero(self) -> None:
        from traininglogs.agent.providers import AnthropicProvider

        with patch("traininglogs.agent.providers.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            tool_block = MagicMock()
            tool_block.type = "tool_use"
            tool_block.input = VALID_STRENGTH_RAW
            mock_client.messages.create.return_value = MagicMock(content=[tool_block])
            mock_cls.return_value = mock_client

            provider = AnthropicProvider()
            provider.extract(
                "some text",
                TrainingLogLLMExtract.model_json_schema(),
                "a system prompt",
                "extract_workout",
                "a tool description",
            )

            _, kwargs = mock_client.messages.create.call_args
            assert kwargs["temperature"] == 0

    def test_groq_provider_pins_temperature_zero(self) -> None:
        import groq

        from traininglogs.agent.providers import GroqProvider

        with patch.object(groq, "Groq") as mock_cls:
            mock_client = MagicMock()
            tool_call = MagicMock()
            tool_call.function.arguments = "{}"
            message = MagicMock(content="", tool_calls=[tool_call])
            mock_client.chat.completions.create.return_value = MagicMock(
                choices=[MagicMock(message=message)]
            )
            mock_cls.return_value = mock_client

            provider = GroqProvider()
            provider.extract(
                "some text",
                TrainingLogLLMExtract.model_json_schema(),
                "a system prompt",
                "extract_workout",
                "a tool description",
            )

            _, kwargs = mock_client.chat.completions.create.call_args
            assert kwargs["temperature"] == 0


class TestProviderParametrization:
    """Providers must use the caller-supplied system prompt / tool name / tool description —
    not a hardcoded module constant — so the same provider can serve the splitter, shell, and
    worker calls added later in the orchestration refactor."""

    def test_anthropic_provider_uses_caller_supplied_prompt_and_tool(self) -> None:
        from traininglogs.agent.providers import AnthropicProvider

        with patch("traininglogs.agent.providers.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            tool_block = MagicMock()
            tool_block.type = "tool_use"
            tool_block.input = VALID_STRENGTH_RAW
            mock_client.messages.create.return_value = MagicMock(content=[tool_block])
            mock_cls.return_value = mock_client

            provider = AnthropicProvider()
            provider.extract(
                "some text",
                TrainingLogLLMExtract.model_json_schema(),
                "a custom system prompt",
                "custom_tool",
                "a custom tool description",
            )

            _, kwargs = mock_client.messages.create.call_args
            assert kwargs["system"] == "a custom system prompt"
            assert kwargs["tools"][0]["name"] == "custom_tool"
            assert kwargs["tools"][0]["description"] == "a custom tool description"
            assert kwargs["tool_choice"] == {"type": "tool", "name": "custom_tool"}

    def test_groq_provider_uses_caller_supplied_prompt_and_tool(self) -> None:
        import groq

        from traininglogs.agent.providers import GroqProvider

        with patch.object(groq, "Groq") as mock_cls:
            mock_client = MagicMock()
            tool_call = MagicMock()
            tool_call.function.arguments = "{}"
            message = MagicMock(content="", tool_calls=[tool_call])
            mock_client.chat.completions.create.return_value = MagicMock(
                choices=[MagicMock(message=message)]
            )
            mock_cls.return_value = mock_client

            provider = GroqProvider()
            provider.extract(
                "some text",
                TrainingLogLLMExtract.model_json_schema(),
                "a custom system prompt",
                "custom_tool",
                "a custom tool description",
            )

            _, kwargs = mock_client.chat.completions.create.call_args
            assert kwargs["messages"][0] == {"role": "system", "content": "a custom system prompt"}
            assert kwargs["tools"][0]["function"]["name"] == "custom_tool"
            assert kwargs["tools"][0]["function"]["description"] == "a custom tool description"
            assert kwargs["tool_choice"] == {"type": "function", "function": {"name": "custom_tool"}}


class TestSystemPromptSessionNotesAndRemarks:
    """Guard the prompt text for the session-notes / remark-attachment / no-alias-list
    decisions (design session before v3.0.0 Step 6). If someone edits SYSTEM_PROMPT and
    these vanish, real extraction will silently regress even though schema tests pass."""

    def test_movement_is_no_longer_a_focus_alias(self) -> None:
        assert '"Focus:", "Movement:", "Muscle Group:"' not in SYSTEM_PROMPT
        assert '"Focus:", "Muscle Group:"' in SYSTEM_PROMPT

    def test_prompt_never_maintains_a_keyword_alias_list(self) -> None:
        assert "do not maintain a running list of every possible keyword" in SYSTEM_PROMPT
        assert 'treat "Movement:" the same as any' in SYSTEM_PROMPT

    def test_prompt_defines_top_level_session_notes_field(self) -> None:
        assert "notes (top-level, session): remarks that don't belong to any specific exercise" in SYSTEM_PROMPT

    def test_prompt_never_silently_drops_unmapped_text(self) -> None:
        assert "Never silently drop text you cannot map to a structured field" in SYSTEM_PROMPT
        assert "the MOST SPECIFIC level it clearly belongs to" in SYSTEM_PROMPT

    def test_prompt_defines_remark_rpe_defaults_to_last_set(self) -> None:
        assert "apply it to the LAST set of that exercise only" in SYSTEM_PROMPT
        assert "Never apply one exercise-level RPE value to every set in the exercise" in SYSTEM_PROMPT

    def test_prompt_lets_named_set_override_last_set_default(self) -> None:
        assert "apply it to that named set instead of the last one" in SYSTEM_PROMPT
