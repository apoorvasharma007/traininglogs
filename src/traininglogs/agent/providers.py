from __future__ import annotations

import copy
import os
from typing import Any, Callable, Protocol, runtime_checkable

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
    # For failures where there is no tool call to replay: the API rejected the request before
    # answering, or answered without calling the tool. A plain user turn is the only shape
    # available, because a tool_result must reference a tool_use id that doesn't exist here.
    return {
        "role": "user",
        "content": (
            f"The previous attempt failed:\n{last_error}\n"
            "Please fix the issue and call the tool again."
        ),
    }


def _tool_error_turns(tool_use_id: str, tool_name: str, sent_input: dict, error: str) -> list[dict]:
    """The two turns that tell the model its own tool call was wrong.

    This is the documented shape for an invalid tool call: replay the assistant's tool_use, then
    answer it with a tool_result carrying is_error. The model sees exactly what it sent and what
    was wrong with it, which is what a plain text nudge cannot convey.

    Both turns are always appended together. A tool_result must immediately follow its
    corresponding tool_use in the history -- a dangling tool_use, or a tool_result with no
    matching call, is rejected by the API."""
    return [
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": tool_use_id, "name": tool_name, "input": sent_input}
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": (
                        f"{error}\n\nCall the tool again with this corrected."
                    ),
                    "is_error": True,
                }
            ],
        },
    ]


def strict_schema(schema: dict) -> dict:
    """Prepare a Pydantic-generated schema for `strict: true`.

    Strict mode constrains token sampling to the grammar compiled from this schema, so a tool
    call that omits a required field or uses the wrong type cannot be produced at all. That is
    strictly better than catching it afterwards: on 2026-08-06 a worker returned `{"number": 1}`
    with `name` missing, and under strict mode that output is unreachable.

    The one thing it requires that Pydantic doesn't emit is `additionalProperties: false` on
    every object. Everything else already satisfies it -- internal $defs, no recursion, and none
    of the unsupported keywords (minimum/maxLength/pattern/format), which is verified by test.

    Note what this does NOT guarantee: that the call is *meaningful*. `{"number": 1, "name":
    "Leg Extension"}` with no sets is schema-valid and strict mode will happily produce it. That
    case is caught by ExerciseExtract's own validation, via the retry loop."""
    out = copy.deepcopy(schema)

    def mark(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
            for value in node.values():
                mark(value)
        elif isinstance(node, list):
            for value in node:
                mark(value)

    mark(out)
    return out


@runtime_checkable
class ExtractionProvider(Protocol):
    def extract(
        self,
        text: str,
        tool_schema: dict,
        system_prompt: str,
        tool_name: str,
        tool_description: str,
        validate: Callable[[dict], Any] | None = None,
    ) -> dict:
        """`validate` is called on the tool payload before it is returned. If it raises, the
        provider re-asks with the error rather than handing the bad payload to the caller.

        This is the whole point of passing it down: validation used to live in the caller, one
        layer above the retry loop, so the retry budget could never be spent on the most common
        failure -- a tool call that parses as JSON but doesn't satisfy the model it's meant to
        fill. Callers keep their own validation as the final check."""
        ...


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
        validate: Callable[[dict], Any] | None = None,
    ) -> dict:
        messages: list[dict] = [{"role": "user", "content": text}]
        last_error: str = ""

        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = self._client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    # Extraction, not creative writing — sampling variety has no upside when the
                    # correct answer is already written in the text. This is greedy decoding, not
                    # a determinism guarantee: identical requests are very likely but not
                    # promised to return identical output.
                    temperature=0,
                    system=system_prompt,
                    tools=[
                        {
                            "name": tool_name,
                            "description": tool_description,
                            "input_schema": strict_schema(tool_schema),
                            # Constrains sampling to the schema, so a call that omits a required
                            # field or mistypes one cannot be generated. See strict_schema().
                            "strict": True,
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
                messages.append(_reask_message(last_error))
                continue

            tool_block = next(
                (b for b in response.content if b.type == "tool_use"),
                None,
            )
            if tool_block is None:
                last_error = "No tool call in response."
                messages.append(_reask_message(last_error))
                continue

            payload = dict(tool_block.input)
            if validate is None:
                return payload
            try:
                validate(payload)
                return payload
            except Exception as exc:
                last_error = str(exc)
                messages.extend(
                    _tool_error_turns(tool_block.id, tool_name, payload, last_error)
                )

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
        validate: Callable[[dict], Any] | None = None,
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
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    max_tokens=self.max_tokens,
                    # Extraction, not creative writing — see the note in AnthropicProvider.
                    # No `strict` here: that is an Anthropic tool-definition field, and this
                    # provider talks to an OpenAI-compatible API. Groq gets the same protection
                    # from `validate` below, just after the fact rather than by construction.
                    temperature=0,
                )
            except groq.BadRequestError as exc:
                # The API's own server-side schema check rejected the tool call before
                # returning a response — there's nothing to inspect, only the error to reask
                # with. Same reask budget as a validation failure we catch ourselves.
                last_error = str(exc)
                if not _is_retryable_bad_request(last_error):
                    raise LLMParserError(f"Non-retryable API error: {last_error}") from exc
                messages.append(_reask_message(last_error))
                continue

            tool_calls = response.choices[0].message.tool_calls

            if not tool_calls:
                last_error = "No tool call in response."
                messages.append(_reask_message(last_error))
                continue

            call = tool_calls[0]
            try:
                payload = json.loads(call.function.arguments)
            except Exception as exc:
                last_error = str(exc)
                messages.append(_reask_message(last_error))
                continue

            if validate is None:
                return payload
            try:
                validate(payload)
                return payload
            except Exception as exc:
                last_error = str(exc)
                # OpenAI-compatible equivalent of replaying the call and answering it with an
                # error: the assistant turn carrying tool_calls, then a `tool` role turn keyed
                # to the same id.
                messages.extend(
                    [
                        {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": call.id,
                                    "type": "function",
                                    "function": {
                                        "name": call.function.name,
                                        "arguments": call.function.arguments,
                                    },
                                }
                            ],
                        },
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": f"{last_error}\n\nCall the tool again with this corrected.",
                        },
                    ]
                )

        raise LLMParserError(
            f"Groq extraction failed after {_MAX_RETRIES + 1} attempts. Last error: {last_error}"
        )
