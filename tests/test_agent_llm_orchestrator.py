"""Unit tests for LLMOrchestrator. No real LLM calls — stub providers and renderers.

TestLLMOrchestrator below exercises the confirm/correct/render loop mechanics with
use_monolithic_parser=True and a single-shape StubProvider — those mechanics (rendering,
reading input, applying a correction, looping) don't depend on which extraction path produced
the initial extract, so they're tested once against the simpler single-call shape.
TestLLMOrchestratorDefaultsToSplitExtraction covers the actual default path (assemble()) and
the flag/env escape hatch back to the monolithic path, per Step 8 of the orchestration
refactor plan."""
from __future__ import annotations

import io
import re
from typing import Any
from unittest.mock import MagicMock

import pytest


from traininglogs.agent.extraction import SEGMENT_TOOL_NAME, SHELL_TOOL_NAME, WORKER_TOOL_NAME
from traininglogs.agent.extraction import TOOL_NAME as MONOLITHIC_TOOL_NAME
from traininglogs.agent.llm_orchestrator import USE_MONOLITHIC_PARSER_ENV_VAR, LLMOrchestrator
from traininglogs.agent.schemas import LLMParserError, TrainingLogLLMExtract
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

    def extract(
        self, text: str, tool_schema: dict, system_prompt: str, tool_name: str,
        tool_description: str, validate=None
    ) -> dict:
        raw = self._responses[min(self._idx, len(self._responses) - 1)]
        self._idx += 1
        return raw


class AlwaysFailProvider:
    def extract(
        self, text: str, tool_schema: dict, system_prompt: str, tool_name: str,
        tool_description: str, validate=None
    ) -> dict:
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
            use_monolithic_parser=True,
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
            use_monolithic_parser=True,
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
            use_monolithic_parser=True,
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
            use_monolithic_parser=True,
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
            use_monolithic_parser=True,
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
            use_monolithic_parser=True,
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
            use_monolithic_parser=True,
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
            use_monolithic_parser=True,
        )
        result = orch.run("session text")
        output = buf.getvalue()
        assert "Bench Press" in output
        assert result.date == "2026-05-12"


class ScriptedProvider:
    """Dispatches by tool_name so one provider instance can serve the segment/shell/worker
    calls assemble() makes, plus (via a separate correction_provider in real usage) the
    monolithic-shaped correction tool."""

    def __init__(
        self,
        split_raw: dict[str, Any],
        shell_raw: dict[str, Any],
        exercise_raw_by_position: dict[int, dict[str, Any]],
    ) -> None:
        self._split_raw = split_raw
        self._shell_raw = shell_raw
        self._exercise_raw_by_position = exercise_raw_by_position
        self.tool_names_called: list[str] = []

    def extract(
        self, text: str, tool_schema: dict, system_prompt: str, tool_name: str,
        tool_description: str, validate=None
    ) -> dict:
        self.tool_names_called.append(tool_name)
        if tool_name == SEGMENT_TOOL_NAME:
            return self._split_raw
        if tool_name == SHELL_TOOL_NAME:
            return self._shell_raw
        if tool_name == WORKER_TOOL_NAME:
            # A worker handed an isolated chunk is given no position at all — there is exactly
            # one exercise in the text. Only the full-document fallback names a number.
            match = re.search(r"extract number (\d+)", text)
            position = int(match.group(1)) if match else 1
            return self._exercise_raw_by_position[position]
        raise AssertionError(f"unexpected tool_name: {tool_name}")


_SPLIT_RAW: dict[str, Any] = {
    "exercises": [{"position": 1, "name": "Bench Press", "anchor": "Bench Press"}]
}
_SHELL_RAW: dict[str, Any] = {"date": "2026-05-12", "focus": "Upper"}
_EXERCISE_RAW_BY_POSITION: dict[int, dict[str, Any]] = {
    1: {
        "number": 1,
        "name": "Bench Press",
        "sets": [{"number": 1, "weight_kg": 80.0, "rep_count": {"full": 8, "partial": 0}}],
        "uncertain_fields": [],
    }
}


class TestLLMOrchestratorDefaultsToSplitExtraction:
    def test_default_calls_segment_shell_and_worker_not_the_monolithic_tool(self) -> None:
        provider = ScriptedProvider(_SPLIT_RAW, _SHELL_RAW, _EXERCISE_RAW_BY_POSITION)
        renderer = _stub_renderer()
        orch = LLMOrchestrator(
            parser_provider=provider,
            correction_provider=provider,
            renderer=renderer,
            input_fn=lambda: "y",
        )
        result = orch.run("session text")

        assert result.date == "2026-05-12"
        assert [e.name for e in result.exercises] == ["Bench Press"]
        assert provider.tool_names_called == [SEGMENT_TOOL_NAME, SHELL_TOOL_NAME, WORKER_TOOL_NAME]
        assert MONOLITHIC_TOOL_NAME not in provider.tool_names_called

    def test_use_monolithic_parser_flag_switches_back(self) -> None:
        provider = StubProvider(_BASE_RAW)
        renderer = _stub_renderer()
        orch = LLMOrchestrator(
            parser_provider=provider,
            correction_provider=provider,
            renderer=renderer,
            input_fn=lambda: "y",
            use_monolithic_parser=True,
        )
        result = orch.run("session text")
        assert result.date == "2026-05-12"

    def test_env_var_switches_to_monolithic_parser_without_the_constructor_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(USE_MONOLITHIC_PARSER_ENV_VAR, "1")
        provider = StubProvider(_BASE_RAW)
        renderer = _stub_renderer()
        orch = LLMOrchestrator(
            parser_provider=provider,
            correction_provider=provider,
            renderer=renderer,
            input_fn=lambda: "y",
        )
        result = orch.run("session text")
        assert result.date == "2026-05-12"

    def test_correction_after_split_extraction_uses_the_monolithic_correction_tool(self) -> None:
        """Corrections always go through LLMExtractValidator's single-call tool regardless of
        which path produced the initial extract — a different provider (or the same one, in
        real usage) can serve both shapes."""
        parser_provider = ScriptedProvider(_SPLIT_RAW, _SHELL_RAW, _EXERCISE_RAW_BY_POSITION)
        correction_provider = StubProvider(dict(_BASE_RAW, focus="Lower"))
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
