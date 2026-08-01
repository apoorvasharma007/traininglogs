"""Unit tests for LLMExtractValidator. No real LLM calls — stub providers only."""
from __future__ import annotations

from typing import Any

import pytest

from traininglogs.agent.llm_extract_validator import LLMExtractValidator
from traininglogs.agent.schemas import LLMParserError, TrainingLogLLMExtract


_VALID_RAW: dict[str, Any] = {
    "date": "2026-05-12",
    "focus": "Upper",
    "exercises": [
        {
            "number": 1,
            "name": "Bench Press",
            "exercise_type": "strength",
            "sets": [
                {
                    "set_type": "strength",
                    "number": 1,
                    "weight_kg": 80.0,
                    "rep_count": {"full": 8, "partial": 0},
                    "rpe": 8.0,
                }
            ],
        }
    ],
    "uncertain_fields": [],
}


class StubProvider:
    """Returns a fixed dict on every extract() call."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self._raw = raw
        self.calls: list[tuple[str, dict]] = []

    def extract(self, text: str, tool_schema: dict) -> dict:
        self.calls.append((text, tool_schema))
        return self._raw


class InvalidProvider:
    """Returns a dict that fails Pydantic validation."""

    def extract(self, text: str, tool_schema: dict) -> dict:
        return {"date": "not-a-date", "exercises": []}


class FailingProvider:
    """Raises LLMParserError on every call."""

    def extract(self, text: str, tool_schema: dict) -> dict:
        raise LLMParserError("provider always fails")


class TestLLMExtractValidator:
    def _make_extract(self, overrides: dict[str, Any] | None = None) -> TrainingLogLLMExtract:
        raw = dict(_VALID_RAW)
        if overrides:
            raw.update(overrides)
        return TrainingLogLLMExtract.model_validate(raw)

    def test_returns_updated_extract(self) -> None:
        updated_raw = dict(_VALID_RAW, focus="Lower")
        provider = StubProvider(updated_raw)
        validator = LLMExtractValidator(provider)
        extract = self._make_extract()

        result = validator.apply_correction(extract, "change focus to Lower")

        assert result.focus == "Lower"

    def test_provider_called_once(self) -> None:
        provider = StubProvider(_VALID_RAW)
        validator = LLMExtractValidator(provider)
        extract = self._make_extract()

        validator.apply_correction(extract, "fix something")

        assert len(provider.calls) == 1

    def test_correction_text_in_prompt(self) -> None:
        provider = StubProvider(_VALID_RAW)
        validator = LLMExtractValidator(provider)
        extract = self._make_extract()

        validator.apply_correction(extract, "the weight was 90kg not 80kg")

        prompt, _ = provider.calls[0]
        assert "the weight was 90kg not 80kg" in prompt

    def test_current_extract_json_in_prompt(self) -> None:
        provider = StubProvider(_VALID_RAW)
        validator = LLMExtractValidator(provider)
        extract = self._make_extract()

        validator.apply_correction(extract, "correction")

        prompt, _ = provider.calls[0]
        assert "Bench Press" in prompt

    def test_tool_schema_passed_to_provider(self) -> None:
        provider = StubProvider(_VALID_RAW)
        validator = LLMExtractValidator(provider)
        extract = self._make_extract()

        validator.apply_correction(extract, "correction")

        _, schema = provider.calls[0]
        assert isinstance(schema, dict)
        assert "exercises" in str(schema)

    def test_invalid_corrected_extract_raises_llm_parser_error(self) -> None:
        provider = InvalidProvider()
        validator = LLMExtractValidator(provider)
        extract = self._make_extract()

        with pytest.raises(LLMParserError, match="failed validation"):
            validator.apply_correction(extract, "some correction")

    def test_provider_failure_propagates(self) -> None:
        provider = FailingProvider()
        validator = LLMExtractValidator(provider)
        extract = self._make_extract()

        with pytest.raises(LLMParserError, match="provider always fails"):
            validator.apply_correction(extract, "some correction")

    def test_uncertain_fields_preserved_from_corrected_extract(self) -> None:
        updated_raw = dict(_VALID_RAW, uncertain_fields=["exercises.0.sets.0.rpe"])
        provider = StubProvider(updated_raw)
        validator = LLMExtractValidator(provider)
        extract = self._make_extract()

        result = validator.apply_correction(extract, "not sure about RPE")

        assert "exercises.0.sets.0.rpe" in result.uncertain_fields
