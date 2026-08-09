"""AnthropicProvider.calls: one record per extract() call, appended in `finally` regardless of
outcome. Feeds the llm_calls table (roadmap D4), keeps the raw tool-call payload even when
validation rejects it (D6), and is what a caller checks to tell "the API answered" apart from
"the answer was usable" (D7) without having to parse console output.

Mocked clients only -- no real API calls, same convention as test_agent_providers_retry.py."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from traininglogs.agent.providers import PRICING, AnthropicProvider
from traininglogs.agent.schemas import LLMParserError

VALID_RAW = {"date": "2026-05-12", "exercises": []}


def _usage(input_tokens: int, output_tokens: int) -> MagicMock:
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    return usage


def _tool_response(payload: dict, input_tokens: int = 100, output_tokens: int = 50) -> MagicMock:
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = payload
    tool_block.id = "tool_use_1"
    return MagicMock(content=[tool_block], usage=_usage(input_tokens, output_tokens))


def _bad_request_error(message: str):
    import anthropic

    response = httpx.Response(status_code=400, request=httpx.Request("POST", "https://example.com"))
    return anthropic.BadRequestError(message, response=response, body=None)


class TestOneRecordPerCall:
    def test_a_successful_call_is_recorded(self) -> None:
        with patch("traininglogs.agent.providers.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _tool_response(VALID_RAW, 120, 40)
            mock_cls.return_value = mock_client

            provider = AnthropicProvider()
            provider.extract("text", {}, "system", "worker", "desc")

            assert len(provider.calls) == 1
            record = provider.calls[0]
            assert record["step"] == "worker"
            assert record["model"] == provider.model
            assert record["attempts"] == 1
            assert record["input_tokens"] == 120
            assert record["output_tokens"] == 40
            assert record["failed"] is None
            assert record["cached"] is False
            assert record["raw_payload"] == VALID_RAW

    def test_cost_is_computed_from_pricing(self) -> None:
        with patch("traininglogs.agent.providers.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _tool_response(VALID_RAW, 1_000_000, 1_000_000)
            mock_cls.return_value = mock_client

            provider = AnthropicProvider()
            provider.extract("text", {}, "system", "worker", "desc")

            price_in, price_out = PRICING[provider.model]
            assert provider.calls[0]["cost_usd"] == pytest.approx(price_in + price_out)

    def test_multiple_calls_each_get_their_own_record(self) -> None:
        with patch("traininglogs.agent.providers.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _tool_response(VALID_RAW)
            mock_cls.return_value = mock_client

            provider = AnthropicProvider()
            provider.extract("text", {}, "system", "segment", "desc")
            provider.extract("text", {}, "system", "worker", "desc")

            assert [c["step"] for c in provider.calls] == ["segment", "worker"]

    def test_a_retried_call_records_the_true_attempt_count(self) -> None:
        with patch("traininglogs.agent.providers.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = [
                _bad_request_error("expected string, but got array"),
                _tool_response(VALID_RAW),
            ]
            mock_cls.return_value = mock_client

            provider = AnthropicProvider()
            provider.extract("text", {}, "system", "worker", "desc")

            assert provider.calls[0]["attempts"] == 2

    def test_exhausted_retries_is_recorded_as_failed_but_not_dropped(self) -> None:
        with patch("traininglogs.agent.providers.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = _bad_request_error("missing properties: exercise")
            mock_cls.return_value = mock_client

            provider = AnthropicProvider()
            with pytest.raises(LLMParserError):
                provider.extract("text", {}, "system", "worker", "desc")

            assert len(provider.calls) == 1, "a call that ultimately fails must still be recorded"
            assert provider.calls[0]["failed"] is not None
            assert "missing properties" in provider.calls[0]["failed"]


class TestRawPayloadSurvivesAValidationFailure:
    """D6: a validation failure should not also cost the response that triggered it.

    Before this, a payload that failed `validate()` on every attempt was discarded the moment
    LLMParserError was raised -- nothing about what the model actually sent survived to be
    inspected. `raw_payload` on the call record is that response, kept regardless."""

    def test_a_payload_rejected_on_every_attempt_is_still_preserved(self) -> None:
        bad_payload = {"date": "not-a-date"}

        def always_reject(payload: dict) -> None:
            raise ValueError("date is not a valid date")

        with patch("traininglogs.agent.providers.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create.return_value = _tool_response(bad_payload)
            mock_cls.return_value = mock_client

            provider = AnthropicProvider()
            with pytest.raises(LLMParserError):
                provider.extract("text", {}, "system", "worker", "desc", validate=always_reject)

        assert provider.calls[0]["failed"] is not None
        assert provider.calls[0]["raw_payload"] == bad_payload, (
            "the rejected payload must survive the failure, not just the error message"
        )

    def test_an_eventual_success_records_the_payload_that_was_returned(self) -> None:
        bad_payload = {"date": "not-a-date"}

        def fussy_validate(payload: dict) -> None:
            if payload == bad_payload:
                raise ValueError("date is not a valid date")

        with patch("traininglogs.agent.providers.anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_client.messages.create.side_effect = [
                _tool_response(bad_payload),
                _tool_response(VALID_RAW),
            ]
            mock_cls.return_value = mock_client

            provider = AnthropicProvider()
            result = provider.extract(
                "text", {}, "system", "worker", "desc", validate=fussy_validate
            )

        assert result == VALID_RAW
        assert provider.calls[0]["raw_payload"] == VALID_RAW
        assert provider.calls[0]["failed"] is None
