from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

import anthropic

from traininglogs.agent.schemas import LLMParserError

DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
_MAX_RETRIES = 2

# Ceiling on a single call's output. Shared by both providers so they cannot drift apart --
# GroqProvider previously set none at all, and OpenAI-compatible APIs reserve
# `input + max_tokens` against the per-minute token budget, so an unset ceiling reserves the
# model's full completion length on every call. On Groq's free tier (8,000 tokens/minute) that
# exhausted the window after two or three calls whose actual usage was a fraction of it.
#
# 4096 is generous for one exercise -- observed worker outputs run 300-1,500 tokens -- while
# staying well clear of the ceiling that truncated the monolithic path's 3.6-4.1K outputs.
DEFAULT_MAX_TOKENS = 4096


# A 400 covers two very different things: the model produced a tool call the API's schema
# check rejected (re-asking can fix it), and the account/request is unusable no matter what we
# send (re-asking cannot). Re-asking the second kind just triples latency on a guaranteed
# failure and buries the real cause under a generic "failed after 3 attempts".
_NON_RETRYABLE_400_MARKERS = (
    "credit balance is too low",
    "billing",
    "quota",
    "not allowed to sample from this model",
    "permission",
)


def _is_retryable_bad_request(message: str) -> bool:
    lowered = message.lower()
    return not any(marker in lowered for marker in _NON_RETRYABLE_400_MARKERS)


def _reask_message(last_error: str) -> dict:
    # A plain follow-up user turn, not a replayed assistant turn — a rejected tool call (the
    # API's own schema check failing it) never produces a response to replay in the first
    # place, so this is the one retry shape that works uniformly for every failure kind.
    return {
        "role": "user",
        "content": (
            f"The previous attempt failed:\n{last_error}\n"
            "Please fix the issue and call the tool again."
        ),
    }


@runtime_checkable
class ExtractionProvider(Protocol):
    def extract(
        self,
        text: str,
        tool_schema: dict,
        system_prompt: str,
        tool_name: str,
        tool_description: str,
    ) -> dict: ...


class AnthropicProvider:
    def __init__(
        self, model: str = DEFAULT_ANTHROPIC_MODEL, max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    def extract(
        self,
        text: str,
        tool_schema: dict,
        system_prompt: str,
        tool_name: str,
        tool_description: str,
    ) -> dict:
        messages: list[dict] = [{"role": "user", "content": text}]
        last_error: str = ""

        for attempt in range(_MAX_RETRIES + 1):
            if attempt > 0:
                messages.append(_reask_message(last_error))

            try:
                response = self._client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    # Extraction, not creative writing — same input must produce the same fields.
                    temperature=0,
                    system=system_prompt,
                    tools=[
                        {
                            "name": tool_name,
                            "description": tool_description,
                            "input_schema": tool_schema,
                        }
                    ],
                    tool_choice={"type": "tool", "name": tool_name},
                    messages=messages,
                )
            except anthropic.BadRequestError as exc:
                # The API's own server-side schema check rejected the tool call before
                # returning a response — there's nothing to inspect, only the error to reask
                # with. Same reask budget as a validation failure we catch ourselves.
                last_error = str(exc)
                if not _is_retryable_bad_request(last_error):
                    raise LLMParserError(f"Non-retryable API error: {last_error}") from exc
                continue

            tool_block = next(
                (b for b in response.content if b.type == "tool_use"),
                None,
            )
            if tool_block is None:
                last_error = "No tool call in response."
                continue

            try:
                return dict(tool_block.input)
            except Exception as exc:
                last_error = str(exc)

        raise LLMParserError(
            f"LLM extraction failed after {_MAX_RETRIES + 1} attempts. Last error: {last_error}"
        )


class GroqProvider:
    def __init__(
        self, model: str = DEFAULT_GROQ_MODEL, max_tokens: int = DEFAULT_MAX_TOKENS
    ) -> None:
        import groq

        self.model = model
        self.max_tokens = max_tokens
        self._client = groq.Groq(api_key=os.environ.get("GROQ_API_KEY"))

    def extract(
        self,
        text: str,
        tool_schema: dict,
        system_prompt: str,
        tool_name: str,
        tool_description: str,
    ) -> dict:
        import groq
        import json

        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]
        tools = [
            {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_description,
                    "parameters": tool_schema,
                },
            }
        ]
        tool_choice = {"type": "function", "function": {"name": tool_name}}
        last_error: str = ""

        for attempt in range(_MAX_RETRIES + 1):
            if attempt > 0:
                messages.append(_reask_message(last_error))

            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    max_tokens=self.max_tokens,
                    # Extraction, not creative writing — same input must produce the same fields.
                    temperature=0,
                )
            except groq.BadRequestError as exc:
                # The API's own server-side schema check rejected the tool call before
                # returning a response — there's nothing to inspect, only the error to reask
                # with. Same reask budget as a validation failure we catch ourselves.
                last_error = str(exc)
                if not _is_retryable_bad_request(last_error):
                    raise LLMParserError(f"Non-retryable API error: {last_error}") from exc
                continue

            tool_calls = response.choices[0].message.tool_calls

            if not tool_calls:
                last_error = "No tool call in response."
                continue

            try:
                return json.loads(tool_calls[0].function.arguments)
            except Exception as exc:
                last_error = str(exc)

        raise LLMParserError(
            f"Groq extraction failed after {_MAX_RETRIES + 1} attempts. Last error: {last_error}"
        )
