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
