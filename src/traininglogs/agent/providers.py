from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

import anthropic

from traininglogs.agent.prompts import SYSTEM_PROMPT
from traininglogs.agent.schemas import LLMParserError

DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
_TOOL_NAME = "extract_workout"
_MAX_RETRIES = 2


@runtime_checkable
class ExtractionProvider(Protocol):
    def extract(self, text: str, tool_schema: dict) -> dict: ...


class AnthropicProvider:
    def __init__(self, model: str = DEFAULT_ANTHROPIC_MODEL) -> None:
        self.model = model
        self._client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    def extract(self, text: str, tool_schema: dict) -> dict:
        messages: list[dict] = [{"role": "user", "content": text}]
        last_error: str = ""

        for attempt in range(_MAX_RETRIES + 1):
            if attempt > 0:
                messages += [
                    {"role": "assistant", "content": _last_response_content},
                    {
                        "role": "user",
                        "content": (
                            f"The extracted data failed validation:\n{last_error}\n"
                            "Please fix the issues and call the tool again."
                        ),
                    },
                ]

            response = self._client.messages.create(
                model=self.model,
                max_tokens=4096,
                # Extraction, not creative writing — same input must produce the same fields.
                temperature=0,
                system=SYSTEM_PROMPT,
                tools=[
                    {
                        "name": _TOOL_NAME,
                        "description": "Extract structured workout data from the session text.",
                        "input_schema": tool_schema,
                    }
                ],
                tool_choice={"type": "tool", "name": _TOOL_NAME},
                messages=messages,
            )

            _last_response_content = response.content

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
    def __init__(self, model: str = DEFAULT_GROQ_MODEL) -> None:
        import groq

        self.model = model
        self._client = groq.Groq(api_key=os.environ.get("GROQ_API_KEY"))

    def extract(self, text: str, tool_schema: dict) -> dict:
        import json

        messages: list[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ]
        tools = [
            {
                "type": "function",
                "function": {
                    "name": _TOOL_NAME,
                    "description": "Extract structured workout data from the session text.",
                    "parameters": tool_schema,
                },
            }
        ]
        tool_choice = {"type": "function", "function": {"name": _TOOL_NAME}}
        last_error: str = ""

        for attempt in range(_MAX_RETRIES + 1):
            if attempt > 0:
                messages += [
                    {"role": "assistant", "content": _last_response_content},
                    {
                        "role": "user",
                        "content": (
                            f"The extracted data failed validation:\n{last_error}\n"
                            "Please fix the issues and call the tool again."
                        ),
                    },
                ]

            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                # Extraction, not creative writing — same input must produce the same fields.
                temperature=0,
            )

            _last_response_content = response.choices[0].message.content or ""
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
