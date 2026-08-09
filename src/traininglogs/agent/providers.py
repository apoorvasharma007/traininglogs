from __future__ import annotations

import os
import re
import time
from typing import Any, Callable, Protocol, runtime_checkable

import anthropic

from traininglogs.agent.schemas import LLMParserError

DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
_MAX_RETRIES = 2

# Per-million-token USD price (input, output). Used only to populate llm_calls.cost_usd -- an
# observability number, never a gate the way scripts/eval_ab.py's --max-cost is.
PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
}

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


# A 429 is not a bad answer, it is "not yet" — so it must not consume the reask budget, which
# exists for answers that came back wrong. Waiting out a rate limit and re-asking a malformed
# payload are different problems with different right responses.
_MAX_RATE_LIMIT_WAITS = 5
_DEFAULT_RATE_LIMIT_WAIT = 20.0

# Above this, waiting is the wrong answer. A per-minute window reopens in seconds and is worth
# sitting out; an hourly or daily allowance is not, and retrying against it burns minutes to
# learn nothing. On 2026-08-06 that is exactly what happened: the server said the window reopened
# in hours, the wait was mis-parsed as the 20s default, and the run retried six times over 451
# seconds before failing anyway. Past this threshold, stop and say when it reopens.
_MAX_WORTH_WAITING = 120.0

# Groq states durations as "547ms", "7.66s", "1m26.4s", "8h32m". `retry-after` is plain seconds.
_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)\s*(ms|h|m|s)", re.IGNORECASE)
_UNIT_SECONDS = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}


def _parse_duration(raw: object) -> float | None:
    """Seconds from a duration string, or None if it can't be read.

    Must handle every shape the server actually sends. Reading "547ms" as 547 minutes, or
    failing on "8h32m" and silently substituting a default, turns "come back tomorrow" into
    "try again in 20 seconds" — which is how a hard quota looked like a transient blip."""
    text = str(raw).strip()
    if not text:
        return None
    parts = _DURATION_PART.findall(text)
    if parts:
        return sum(float(value) * _UNIT_SECONDS[unit.lower()] for value, unit in parts)
    try:
        return float(text)   # bare `retry-after`, already in seconds
    except ValueError:
        return None


def _rate_limit_wait_seconds(exc: Exception) -> float | None:
    """How long the server says to wait, or None if waiting is not worth it.

    `retry-after` is authoritative; the per-window reset headers are the fallback. None means
    the caller should give up now rather than sit on a window that won't reopen in time."""
    headers = getattr(getattr(exc, "response", None), "headers", None) or {}
    for key in ("retry-after", "x-ratelimit-reset-tokens", "x-ratelimit-reset-requests"):
        seconds = _parse_duration(headers.get(key)) if headers.get(key) else None
        if seconds is None or seconds <= 0:
            continue
        return None if seconds > _MAX_WORTH_WAITING else seconds + 1.0
    return _DEFAULT_RATE_LIMIT_WAIT


def _describe_wait(exc: Exception) -> str:
    """Human-readable reopening time for the give-up message."""
    headers = getattr(getattr(exc, "response", None), "headers", None) or {}
    for key in ("retry-after", "x-ratelimit-reset-tokens", "x-ratelimit-reset-requests"):
        seconds = _parse_duration(headers.get(key)) if headers.get(key) else None
        if seconds and seconds > 0:
            if seconds >= 3600:
                return f"{seconds / 3600:.1f} hours"
            if seconds >= 60:
                return f"{seconds / 60:.0f} minutes"
            return f"{seconds:.0f} seconds"
    return "an unknown amount of time"


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


# DO NOT set `strict: true` on these tool definitions. Measured 2026-08-06, and it is a trap
# for exactly this schema.
#
# Strict mode constrains sampling to a grammar compiled from the schema, which guarantees no
# required field is ever missing. It also enforces the schema's **property order**. Our people
# write warmups above working sets -- `### Warmup Notes` comes before `### Working Sets` -- so
# the model emits in document order: name, warmup_notes, warmup_sets, sets. The schema declares
# name, sets, warmup_sets, notes, warmup_notes. Under the grammar those conflict: once the model
# has emitted `warmup_notes`, `sets` is behind it and can never be produced.
#
# The evidence, from the raw dumps of three runs. Without strict, 8 of 18 Haiku payloads emitted
# keys out of schema order and every one of them carried its sets. With strict, 0 of 10 were out
# of order -- and core accuracy fell from 77.6% to 31.4%, with whole exercises arriving as a name
# and nothing else.
#
# Reordering the fields to match the document would only move the problem: Groq's natural order
# was different again (`name, notes, sets`), and photo/speech input will not follow the markdown
# layout at all. No single order is right for every input.
#
# The failure strict mode was meant to prevent -- a required field missing -- is already handled
# by validating inside the retry loop below, which costs one extra call on the rare bad payload
# instead of silently truncating every good one.


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
        # One record per extract() call -- i.e. per step (segment/shell/worker/correction), not
        # per raw HTTP attempt -- appended in `finally` whether the call ends in success or a
        # raised LLMParserError. ingest/extract.py drains this into the llm_calls table after
        # assemble() returns (roadmap D4). Never read internally; purely so a caller downstream
        # of `text` can see what it cost without threading a logger through every function in
        # between.
        self.calls: list[dict] = []

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
        rate_limit_waits = 0
        attempt = 0
        input_tokens = 0
        output_tokens = 0
        raw_payload: dict | None = None
        succeeded = False
        t0 = time.time()

        try:
            while attempt <= _MAX_RETRIES:
                try:
                    response = self._client.messages.create(
                        model=self.model,
                        max_tokens=self.max_tokens,
                        # Extraction, not creative writing — sampling variety has no upside when
                        # the correct answer is already written in the text. This is greedy
                        # decoding, not a determinism guarantee: identical requests are very
                        # likely but not promised to return identical output.
                        temperature=0,
                        system=system_prompt,
                        tools=[
                            {
                                "name": tool_name,
                                "description": tool_description,
                                "input_schema": tool_schema,
                                # No `strict` here, deliberately — see the note above the class.
                            }
                        ],
                        tool_choice={"type": "tool", "name": tool_name},
                        messages=messages,
                    )
                except anthropic.RateLimitError as exc:
                    wait = _rate_limit_wait_seconds(exc)
                    if wait is None:
                        last_error = (
                            f"Rate limited, and the window does not reopen for "
                            f"{_describe_wait(exc)} — too long to wait out. This is a quota."
                        )
                        raise LLMParserError(f"{last_error} Full response: {exc}") from exc
                    rate_limit_waits += 1
                    if rate_limit_waits > _MAX_RATE_LIMIT_WAITS:
                        last_error = (
                            f"Rate limited {rate_limit_waits} times without the window "
                            f"reopening."
                        )
                        raise LLMParserError(f"{last_error} Full response: {exc}") from exc
                    time.sleep(wait)
                    continue  # deliberately not `attempt += 1` — see _MAX_RATE_LIMIT_WAITS
                except anthropic.BadRequestError as exc:
                    # The API's own server-side schema check rejected the tool call before
                    # returning a response — there's nothing to inspect, only the error to reask
                    # with. Same reask budget as a validation failure we catch ourselves.
                    last_error = str(exc)
                    if not _is_retryable_bad_request(last_error):
                        raise LLMParserError(f"Non-retryable API error: {last_error}") from exc
                    messages.append(_reask_message(last_error))
                    attempt += 1
                    continue

                attempt += 1
                usage = getattr(response, "usage", None)
                if usage is not None:
                    input_tokens += getattr(usage, "input_tokens", 0) or 0
                    output_tokens += getattr(usage, "output_tokens", 0) or 0

                tool_block = next(
                    (b for b in response.content if b.type == "tool_use"),
                    None,
                )
                if tool_block is None:
                    last_error = "No tool call in response."
                    # The call itself succeeded -- the API answered -- it just didn't call the
                    # tool. Conflating this with a transport failure is what misdiagnosed the
                    # `mono` truncation as an outage rather than an unusable result (D7).
                    print(f"[llm] {tool_name}: call succeeded, no tool call in response — reasking")
                    messages.append(_reask_message(last_error))
                    continue

                payload = dict(tool_block.input)
                # Kept even if `validate` rejects it below, so a validation failure does not
                # also cost the response that triggered it (D6) — visible on the llm_calls row
                # via `raw_payload` for whatever attempt is last, not just the final one.
                raw_payload = payload
                if validate is None:
                    succeeded = True
                    return payload
                try:
                    validate(payload)
                    succeeded = True
                    return payload
                except Exception as exc:
                    last_error = str(exc)
                    print(
                        f"[llm] {tool_name}: call succeeded, result not usable — "
                        f"{last_error.splitlines()[0][:160]}"
                    )
                    messages.extend(
                        _tool_error_turns(tool_block.id, tool_name, payload, last_error)
                    )

            raise LLMParserError(
                f"LLM extraction failed after {_MAX_RETRIES + 1} attempts. "
                f"Last error: {last_error}"
            )
        finally:
            elapsed_ms = round((time.time() - t0) * 1000)
            price_in, price_out = PRICING.get(self.model, (0.0, 0.0))
            cost_usd = round(input_tokens / 1e6 * price_in + output_tokens / 1e6 * price_out, 6)
            self.calls.append(
                {
                    "step": tool_name,
                    "model": self.model,
                    "attempts": attempt,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd": cost_usd,
                    "ms": elapsed_ms,
                    "cached": False,
                    "failed": None if succeeded else (last_error or "unknown"),
                    "raw_payload": raw_payload,
                }
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
        rate_limit_waits = 0

        attempt = 0
        while attempt <= _MAX_RETRIES:
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    max_tokens=self.max_tokens,
                    # Extraction, not creative writing — see the note in AnthropicProvider.
                    # Grammar-constrained decoding is not used on either provider — see the
                    # note above AnthropicProvider. `validate` below is what guards the payload.
                    temperature=0,
                )
            except groq.RateLimitError as exc:
                # The free tier meters tokens per minute and reserves `input + max_tokens` on
                # every call, so a handful of worker calls saturates the window. Waiting it out
                # is the correct response and costs only wall-clock time; failing the file is
                # what used to happen, and it made the free verification path unusable.
                wait = _rate_limit_wait_seconds(exc)
                if wait is None:
                    raise LLMParserError(
                        f"Rate limited, and the window does not reopen for "
                        f"{_describe_wait(exc)} — too long to wait out. This is a quota, not a "
                        f"busy moment. Full response: {exc}"
                    ) from exc
                rate_limit_waits += 1
                if rate_limit_waits > _MAX_RATE_LIMIT_WAITS:
                    raise LLMParserError(
                        f"Rate limited {rate_limit_waits} times without the window reopening. "
                        f"Full response: {exc}"
                    ) from exc
                time.sleep(wait)
                continue  # deliberately not `attempt += 1` — see _MAX_RATE_LIMIT_WAITS
            except groq.BadRequestError as exc:
                # The API's own server-side schema check rejected the tool call before
                # returning a response — there's nothing to inspect, only the error to reask
                # with. Same reask budget as a validation failure we catch ourselves.
                last_error = str(exc)
                if not _is_retryable_bad_request(last_error):
                    raise LLMParserError(f"Non-retryable API error: {last_error}") from exc
                messages.append(_reask_message(last_error))
                attempt += 1
                continue

            attempt += 1
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
