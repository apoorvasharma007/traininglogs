"""Unit tests for LLMOrchestrator. No real LLM calls — stub providers and renderers."""
from __future__ import annotations

import io
from typing import Any
from unittest.mock import MagicMock

import pytest


from traininglogs.agent.llm_orchestrator import LLMOrchestrator
from traininglogs.agent.llm_parser import LLMParserError, TrainingLogLLMExtract
from traininglogs.agent.renderer import TerminalRenderer
from rich.console import Console


_BASE_RAW: dict[str, Any] = {
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

_UPDATED_RAW: dict[str, Any] = dict(_BASE_RAW, focus="Lower")


class StubProvider:
    """First call returns base raw; subsequent calls return updated raw."""

    def __init__(self, *responses: dict[str, Any]) -> None:
        self._responses = list(responses)
        self._idx = 0

    def extract(self, text: str, tool_schema: dict) -> dict:
        raw = self._responses[min(self._idx, len(self._responses) - 1)]
        self._idx += 1
        return raw


class AlwaysFailProvider:
    def extract(self, text: str, tool_schema: dict) -> dict:
        raise LLMParserError("always fails")


def _null_console() -> Console:
    return Console(file=io.StringIO(), highlight=False)


def _stub_renderer() -> TerminalRenderer:
    return TerminalRenderer(console=_null_console())


class TestLLMOrchestrator:
    def test_immediate_confirm_returns_extract(self) -> None:
        provider = StubProvider(_BASE_RAW)
        renderer = _stub_renderer()
        orch = LLMOrchestrator(
            parser_provider=provider,
            correction_provider=provider,
            renderer=renderer,
            input_fn=lambda: "y",
        )
        result = orch.run("session text")
        assert isinstance(result, TrainingLogLLMExtract)
        assert result.date == "2026-05-12"

    def test_yes_variant_accepted(self) -> None:
        provider = StubProvider(_BASE_RAW)
        renderer = _stub_renderer()
        orch = LLMOrchestrator(
            parser_provider=provider,
            correction_provider=provider,
            renderer=renderer,
            input_fn=lambda: "yes",
        )
        result = orch.run("session text")
        assert result.date == "2026-05-12"

    def test_one_correction_then_confirm(self) -> None:
        # First parse returns base, first correction returns updated
        parser_provider = StubProvider(_BASE_RAW)
        correction_provider = StubProvider(_UPDATED_RAW)
        renderer = _stub_renderer()
        answers = iter(["change focus to Lower", "y"])
        orch = LLMOrchestrator(
            parser_provider=parser_provider,
            correction_provider=correction_provider,
            renderer=renderer,
            input_fn=lambda: next(answers),
        )
        result = orch.run("session text")
        assert result.focus == "Lower"

    def test_multiple_corrections(self) -> None:
        raw_v2: dict[str, Any] = dict(_BASE_RAW, focus="Push")
        raw_v3: dict[str, Any] = dict(_BASE_RAW, focus="Pull")
        parser_provider = StubProvider(_BASE_RAW)
        correction_provider = StubProvider(raw_v2, raw_v3)
        renderer = _stub_renderer()
        answers = iter(["fix 1", "fix 2", "y"])
        orch = LLMOrchestrator(
            parser_provider=parser_provider,
            correction_provider=correction_provider,
            renderer=renderer,
            input_fn=lambda: next(answers),
        )
        result = orch.run("session text")
        assert result.focus == "Pull"

    def test_renderer_called_each_iteration(self) -> None:
        provider = StubProvider(_BASE_RAW, _UPDATED_RAW)
        mock_renderer = MagicMock(spec=TerminalRenderer)
        mock_renderer.console = _null_console()
        answers = iter(["correction", "y"])
        orch = LLMOrchestrator(
            parser_provider=provider,
            correction_provider=provider,
            renderer=mock_renderer,
            input_fn=lambda: next(answers),
        )
        orch.run("session text")
        assert mock_renderer.render.call_count == 2

    def test_parse_error_propagates(self) -> None:
        provider = AlwaysFailProvider()
        renderer = _stub_renderer()
        orch = LLMOrchestrator(
            parser_provider=provider,
            correction_provider=provider,
            renderer=renderer,
            input_fn=lambda: "y",
        )
        with pytest.raises(LLMParserError, match="always fails"):
            orch.run("session text")

    def test_empty_answer_rerenders_without_correction(self) -> None:
        provider = StubProvider(_BASE_RAW)
        mock_renderer = MagicMock(spec=TerminalRenderer)
        mock_renderer.console = _null_console()
        # Empty answer first, then confirm
        answers = iter(["", "y"])
        orch = LLMOrchestrator(
            parser_provider=provider,
            correction_provider=provider,
            renderer=mock_renderer,
            input_fn=lambda: next(answers),
        )
        result = orch.run("session text")
        # render called twice: once for initial, once after empty answer
        assert mock_renderer.render.call_count == 2
        assert result.date == "2026-05-12"

    def test_integration_card_built_and_rendered(self) -> None:
        """Integration: real builder + real renderer, confirm immediately."""
        provider = StubProvider(_BASE_RAW)
        buf = io.StringIO()
        console = Console(file=buf, highlight=False, width=120)
        renderer = TerminalRenderer(console=console)
        orch = LLMOrchestrator(
            parser_provider=provider,
            correction_provider=provider,
            renderer=renderer,
            input_fn=lambda: "y",
        )
        result = orch.run("session text")
        output = buf.getvalue()
        assert "Bench Press" in output
        assert result.date == "2026-05-12"
