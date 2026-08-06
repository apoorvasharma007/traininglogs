"""Unit tests for the provider-level retry ("reask") fix: AnthropicProvider/GroqProvider now
catch the SDK's own BadRequestError (the API's server-side schema rejection of a malformed
tool call) and retry within the existing budget, feeding the error back to the model — the
same mechanism Guardrails AI/Instructor call "reask." Found missing during live E2E testing:
a rejected tool call previously crashed on the first attempt with zero retries. Mocked clients
only — no real API calls."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from traininglogs.agent.schemas import LLMParserError


def _bad_request_error(exc_cls, message: str):
    response = httpx.Response(status_code=400, request=httpx.Request("POST", "https://example.com"))
    return exc_cls(message, response=response, body=None)


VALID_RAW = {"date": "2026-05-12", "exercises": []}


class TestAnthropicProviderRetriesOnBadRequest:
    def test_retries_after_bad_request_then_succeeds(self) -> None:
        import anthropic

        from traininglogs.agent.providers import AnthropicProvider

        with patch("traininglogs.agent.providers.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            tool_block = MagicMock()
            tool_block.type = "tool_use"
            tool_block.input = VALID_RAW
            success_response = MagicMock(content=[tool_block])

            mock_client.messages.create.side_effect = [
                _bad_request_error(anthropic.BadRequestError, "expected string, but got array"),
                success_response,
            ]
            mock_cls.return_value = mock_client

            provider = AnthropicProvider()
            result = provider.extract("some text", {}, "system prompt", "tool_name", "tool desc")

            assert result == VALID_RAW
            assert mock_client.messages.create.call_count == 2
            _, second_kwargs = mock_client.messages.create.call_args
            reask_contents = [m["content"] for m in second_kwargs["messages"] if m["role"] == "user"]
            assert any("expected string, but got array" in c for c in reask_contents)

    def test_raises_llm_parser_error_after_exhausting_retries(self) -> None:
        import anthropic

        from traininglogs.agent.providers import AnthropicProvider

        with patch("traininglogs.agent.providers.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = _bad_request_error(
                anthropic.BadRequestError, "missing properties: exercise"
            )
            mock_cls.return_value = mock_client

            provider = AnthropicProvider()
            with pytest.raises(LLMParserError, match="missing properties: exercise"):
                provider.extract("some text", {}, "system prompt", "tool_name", "tool desc")

            assert mock_client.messages.create.call_count == 3  # 1 + _MAX_RETRIES


class TestGroqProviderRetriesOnBadRequest:
    def test_retries_after_bad_request_then_succeeds(self) -> None:
        import groq

        from traininglogs.agent.providers import GroqProvider

        with patch.object(groq, "Groq") as mock_cls:
            mock_client = MagicMock()
            tool_call = MagicMock()
            tool_call.function.arguments = '{"date": "2026-05-12", "exercises": []}'
            message = MagicMock(content="", tool_calls=[tool_call])
            success_response = MagicMock(choices=[MagicMock(message=message)])

            mock_client.chat.completions.create.side_effect = [
                _bad_request_error(groq.BadRequestError, "expected object, but got number"),
                success_response,
            ]
            mock_cls.return_value = mock_client

            provider = GroqProvider()
            result = provider.extract("some text", {}, "system prompt", "tool_name", "tool desc")

            assert result == VALID_RAW
            assert mock_client.chat.completions.create.call_count == 2
            _, second_kwargs = mock_client.chat.completions.create.call_args
            reask_contents = [m["content"] for m in second_kwargs["messages"] if m["role"] == "user"]
            assert any("expected object, but got number" in c for c in reask_contents)

    def test_raises_llm_parser_error_after_exhausting_retries(self) -> None:
        import groq

        from traininglogs.agent.providers import GroqProvider

        with patch.object(groq, "Groq") as mock_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = _bad_request_error(
                groq.BadRequestError, "expected string, but got array"
            )
            mock_cls.return_value = mock_client

            provider = GroqProvider()
            with pytest.raises(LLMParserError, match="expected string, but got array"):
                provider.extract("some text", {}, "system prompt", "tool_name", "tool desc")

            assert mock_client.chat.completions.create.call_count == 3  # 1 + _MAX_RETRIES


class TestValidationFailuresReachTheRetryBudget:
    """The gap this closes.

    Until 2026-08-06 the retry loop only ever saw API-level failures. A tool call that came back
    as well-formed JSON was returned straight to the caller, which validated it one layer above
    the loop — so the single most common failure, a payload that parses but doesn't satisfy the
    model it fills, got zero of its three attempts. A live run lost 5 exercises to workers
    returning `{"number": 1}` while the reask budget sat unused."""

    @staticmethod
    def _response(payload: dict, block_id: str = "toolu_1"):
        block = MagicMock()
        block.type = "tool_use"
        block.input = payload
        block.id = block_id
        return MagicMock(content=[block])

    def test_a_payload_that_fails_validation_is_re_asked_not_returned(self) -> None:
        from traininglogs.agent.providers import AnthropicProvider

        def validate(payload: dict) -> None:
            if "name" not in payload:
                raise ValueError("Field required: name")

        with patch("traininglogs.agent.providers.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = [
                self._response({"number": 1}),                    # the real 2026-08-06 failure
                self._response({"name": "Leg Extension"}),
            ]
            mock_cls.return_value = mock_client

            result = AnthropicProvider().extract(
                "chunk", {}, "sys", "extract_exercise", "desc", validate=validate
            )

            assert result == {"name": "Leg Extension"}
            assert mock_client.messages.create.call_count == 2

    def test_the_reask_replays_the_bad_call_and_answers_it_with_is_error(self) -> None:
        """The documented shape for an invalid tool call. A plain text nudge cannot show the
        model what it actually sent; a tool_result keyed to the tool_use id can."""
        from traininglogs.agent.providers import AnthropicProvider

        def validate(payload: dict) -> None:
            if "name" not in payload:
                raise ValueError("Field required: name")

        with patch("traininglogs.agent.providers.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = [
                self._response({"number": 1}, block_id="toolu_abc"),
                self._response({"name": "Leg Extension"}),
            ]
            mock_cls.return_value = mock_client

            AnthropicProvider().extract(
                "chunk", {}, "sys", "extract_exercise", "desc", validate=validate
            )

            messages = mock_client.messages.create.call_args[1]["messages"]
            assistant, result_turn = messages[-2], messages[-1]

            assert assistant["role"] == "assistant"
            assert assistant["content"][0]["type"] == "tool_use"
            assert assistant["content"][0]["id"] == "toolu_abc"
            assert assistant["content"][0]["input"] == {"number": 1}

            # A tool_result must immediately follow its tool_use, and reference the same id.
            assert result_turn["role"] == "user"
            block = result_turn["content"][0]
            assert block["type"] == "tool_result"
            assert block["tool_use_id"] == "toolu_abc"
            assert block["is_error"] is True
            assert "Field required: name" in block["content"]

    def test_every_attempt_failing_validation_raises_rather_than_returning_junk(self) -> None:
        from traininglogs.agent.providers import AnthropicProvider

        def always_invalid(payload: dict) -> None:
            raise ValueError("no working sets and no warmup sets")

        with patch("traininglogs.agent.providers.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = self._response({"name": "Leg Extension"})
            mock_cls.return_value = mock_client

            with pytest.raises(LLMParserError, match="no working sets"):
                AnthropicProvider().extract(
                    "chunk", {}, "sys", "extract_exercise", "desc", validate=always_invalid
                )

            assert mock_client.messages.create.call_count == 3   # the full budget, and no more

    def test_no_validator_means_no_behaviour_change(self) -> None:
        from traininglogs.agent.providers import AnthropicProvider

        with patch("traininglogs.agent.providers.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = self._response({"anything": True})
            mock_cls.return_value = mock_client

            result = AnthropicProvider().extract("chunk", {}, "sys", "tool", "desc")

            assert result == {"anything": True}
            assert mock_client.messages.create.call_count == 1


class TestGroqValidationRetry:
    @staticmethod
    def _response(arguments: str, call_id: str = "call_1"):
        call = MagicMock()
        call.id = call_id
        call.function.name = "extract_exercise"
        call.function.arguments = arguments
        message = MagicMock(tool_calls=[call])
        return MagicMock(choices=[MagicMock(message=message)])

    def test_groq_re_asks_with_the_openai_tool_role_shape(self) -> None:
        """Groq speaks the OpenAI dialect: the error goes back on a `tool` role turn keyed to
        the call id, not as an Anthropic tool_result block."""
        from traininglogs.agent.providers import GroqProvider

        def validate(payload: dict) -> None:
            if "name" not in payload:
                raise ValueError("Field required: name")

        with patch("groq.Groq") as mock_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = [
                self._response('{"number": 1}', call_id="call_xyz"),
                self._response('{"name": "Leg Extension"}'),
            ]
            mock_cls.return_value = mock_client

            result = GroqProvider().extract(
                "chunk", {}, "sys", "extract_exercise", "desc", validate=validate
            )

            assert result == {"name": "Leg Extension"}
            messages = mock_client.chat.completions.create.call_args[1]["messages"]
            assistant, tool_turn = messages[-2], messages[-1]
            assert assistant["role"] == "assistant"
            assert assistant["tool_calls"][0]["id"] == "call_xyz"
            assert tool_turn["role"] == "tool"
            assert tool_turn["tool_call_id"] == "call_xyz"
            assert "Field required: name" in tool_turn["content"]
