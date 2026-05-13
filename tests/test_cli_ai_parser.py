"""
E2E tests for the --parser ai path in `traininglogs validate`.

The LLMOrchestrator is always stubbed — no real API calls are made.
validate does no DB write, so no database connection is needed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from traininglogs.agent.llm_parser import TrainingLogLLMExtract
from traininglogs.cli.validate import main as validate_main



FIXTURES_VALID = Path(__file__).parent / "fixtures" / "valid"

_PATCH_TARGET = "traininglogs.agent.llm_orchestrator.LLMOrchestrator.run"

_MINIMAL_EXTRACT_RAW: dict[str, Any] = {
    "date": "2026-05-12",
    "program": "Test Program",
    "phase": 3,
    "week": 11,
    "focus": "Lower Strength",
    "session_duration_minutes": 90,
    "exercises": [
        {
            "number": 1,
            "name": "Squat",
            "exercise_type": "strength",
            "sets": [
                {
                    "set_type": "strength",
                    "number": 1,
                    "weight_kg": 100.0,
                    "rep_count": {"full": 5, "partial": 0},
                    "rpe": 8.0,
                }
            ],
        }
    ],
    "uncertain_fields": [],
}

_MINIMAL_EXTRACT = TrainingLogLLMExtract.model_validate(_MINIMAL_EXTRACT_RAW)


class TestValidateAiParser:
    def test_ai_parser_exits_zero_on_valid_fixture(self, capsys) -> None:
        fixture = FIXTURES_VALID / "lower_strength_session.md"
        with patch(_PATCH_TARGET, return_value=_MINIMAL_EXTRACT):
            result = validate_main(["--parser", "ai", str(fixture)])
        assert result == 0

    def test_ai_parser_prints_session_summary(self, capsys) -> None:
        fixture = FIXTURES_VALID / "lower_strength_session.md"
        with patch(_PATCH_TARGET, return_value=_MINIMAL_EXTRACT):
            validate_main(["--parser", "ai", str(fixture)])
        out = capsys.readouterr().out
        assert "Valid" in out
        assert "2026-05-12" in out
        assert "Squat" in out

    def test_ai_is_default_parser(self, capsys) -> None:
        fixture = FIXTURES_VALID / "lower_strength_session.md"
        with patch(_PATCH_TARGET, return_value=_MINIMAL_EXTRACT):
            result = validate_main([str(fixture)])
        assert result == 0

    def test_ai_parser_missing_file_exits_nonzero(self) -> None:
        result = validate_main(["--parser", "ai", "nonexistent_file.md"])
        assert result == 1

    def test_ai_parser_propagates_orchestrator_exception(self, capsys) -> None:
        fixture = FIXTURES_VALID / "lower_strength_session.md"
        with patch(_PATCH_TARGET, side_effect=RuntimeError("LLM unavailable")):
            result = validate_main(["--parser", "ai", str(fixture)])
        assert result == 1
        out = capsys.readouterr().out
        assert "Error" in out

    def test_rules_parser_still_works(self, capsys) -> None:
        fixture = FIXTURES_VALID / "lower_strength_session.md"
        result = validate_main(["--parser", "rules", str(fixture)])
        assert result == 0

    def test_all_valid_fixtures_pass_with_ai_stub(self) -> None:
        fixtures = list(FIXTURES_VALID.glob("*.md"))
        assert fixtures, "no fixtures found"
        for fixture in fixtures:
            with patch(_PATCH_TARGET, return_value=_MINIMAL_EXTRACT):
                result = validate_main(["--parser", "ai", str(fixture)])
            assert result == 0, f"Failed for {fixture.name}"

    def test_ai_extract_with_uncertain_fields_still_validates(self, capsys) -> None:
        uncertain_raw = dict(_MINIMAL_EXTRACT_RAW, uncertain_fields=["exercises.0.sets.0.rpe"])
        uncertain_extract = TrainingLogLLMExtract.model_validate(uncertain_raw)
        fixture = FIXTURES_VALID / "lower_strength_session.md"
        with patch(_PATCH_TARGET, return_value=uncertain_extract):
            result = validate_main(["--parser", "ai", str(fixture)])
        assert result == 0
