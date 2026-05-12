from __future__ import annotations

import os
import re
import datetime
from typing import List, Optional, Protocol, runtime_checkable

import anthropic
from pydantic import BaseModel, Field, ValidationError, field_validator

from traininglogs.models.models import Exercise

DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
_TOOL_NAME = "extract_workout"
_MAX_RETRIES = 2

SYSTEM_PROMPT = """You are a structured data extractor for personal strength and conditioning training logs.

Extract the workout data from the user's session text into the extract_workout tool.

Rules:
- date: YYYY-MM-DD format.
- exercises: preserve the order from the text. Each exercise has a sequential number starting at 1.
- set_type: use "strength" for weight/rep sets; use "activity" for cardio/distance/time sets.
- weight_kg: always in kilograms. If the user wrote lbs, convert.
- rpe: must be 1.0–10.0 in whole or half steps (e.g. 8, 8.5). Omit if not stated.
- rep_count: {full: N, partial: M} where partial defaults to 0. "8+1" means full=8, partial=1.
- failure_technique: use the appropriate technique_type — "LLP", "StaticHold", "MyoReps", or "DropSet".
- unilateral sets: use unilateral_rep_count with left/right RepCount objects instead of rep_count.
- warmup sets: number field starts at 1. Use notes="feel" if the user wrote "feel".
- uncertain_fields: list any dot-path field you are not confident about, e.g. "exercises.0.sets.1.rpe".
  Only list fields you actually extracted (not fields you left null).
- Omit fields you cannot determine — do not guess beyond what is written."""


class TrainingLogLLMExtract(BaseModel):
    date: str
    program: Optional[str] = None
    phase: Optional[int] = None
    week: Optional[int] = None
    is_deload_week: Optional[bool] = None
    focus: Optional[str] = None
    session_duration_minutes: Optional[int] = None
    exercises: List[Exercise]
    uncertain_fields: List[str] = Field(default_factory=list)

    @field_validator("date")
    @classmethod
    def valid_date(cls, v: str) -> str:
        if not isinstance(v, str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("Date must be formatted as YYYY-MM-DD")
        try:
            datetime.datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Date is not a valid calendar date: {v}")
        return v


class LLMParserError(Exception):
    pass


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


def parse(text: str, provider: ExtractionProvider | None = None) -> TrainingLogLLMExtract:
    provider = provider or AnthropicProvider()
    tool_schema = TrainingLogLLMExtract.model_json_schema()

    raw = provider.extract(text, tool_schema)

    try:
        return TrainingLogLLMExtract.model_validate(raw)
    except ValidationError as exc:
        raise LLMParserError(
            f"Extracted data did not pass validation:\n{exc}"
        ) from exc
