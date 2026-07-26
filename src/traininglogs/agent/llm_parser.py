from __future__ import annotations

import os
import re
import datetime
from typing import List, Optional, Protocol, runtime_checkable

import anthropic
from pydantic import BaseModel, Field, ValidationError, field_validator

from traininglogs.models.models import Exercise, SessionCooldown, SessionWarmup

DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
_TOOL_NAME = "extract_workout"
_MAX_RETRIES = 2

SYSTEM_PROMPT = """You are a structured data extractor for personal strength and conditioning training logs.

Extract the workout data from the user's session text into the extract_workout tool.

Rules:
- date: YYYY-MM-DD format.
- focus: the session's training focus or movement type (e.g. "Upper Strength", "Bench", "Legs"). Extract from any "Focus:", "Movement:", "Muscle Group:", or session title field. Use the short label, not a long description.
- session_duration_minutes: total session duration as an integer in minutes. Convert any format: "1hr 30min" → 90, "1hrs 41min" → 101, "1:30" → 90, "45min" → 45.
- program: name of the training program if stated, else omit.
- phase: integer phase number. Convert word ordinals: "One"→1, "Two"→2, "Three"→3, etc. Ignore any description after the number (e.g. "One - Volume/Base Building" → 1). Omit only if no phase is mentioned.
- week: integer week number. Extract from any "Week:" field. Omit only if no week is mentioned.
- is_deload_week: true only if explicitly stated as a deload week.
- warmup: movements in a warmup section at the start of the session. Each has a sequential number \
starting at 1, a name, and optionally reps (integer), duration_seconds (integer), or notes.
- exercises: the main working exercises ONLY. Do NOT include warmup or cooldown sections as exercises — they must go in warmup/cooldown fields instead. Preserve order. Each exercise has a sequential number starting at 1.
- cooldown: movements in a cooldown section at the end of the session. Same shape as warmup.
- tags: classify the exercise using one or more of: "absolute_strength", "muscle_growth", \
"muscle_endurance", "explosive_power", "core_stabilization", "balance_control", \
"passive_flexibility", "active_mobility", "cardiorespiratory", "saq", "sport_specific". \
Omit if unclear.
- modality: free-text equipment type, e.g. "barbell", "dumbbell", "cable", "machine", \
"bodyweight", "bands", "kettlebell", "pool". Omit if unclear.
- movement_pattern: list one or more of: "squat", "hip_hinge", "push", "pull", "lunge", \
"carry", "rotation". Omit if unclear.
- weight_kg: always in kilograms. If the user wrote lbs, convert.
- rpe: must be 1.0–10.0 in whole or half steps (e.g. 8, 8.5). Omit if not stated.
- rep_count: {full: N, partial: M} where partial defaults to 0. "8+1" means full=8, partial=1.
- failure_technique: use the appropriate technique_type — "LLP", "StaticHold", "MyoReps", \
or "DropSet".
- unilateral sets: use unilateral_rep_count with left/right RepCount objects instead of rep_count.
- warmup_sets (per exercise): number field starts at 1. rep_count is a plain integer (e.g. 8), NOT an object — do not use {full, partial}. Use notes="feel" if the user wrote "feel".
- modality: single string, not an array (e.g. "barbell", not ["barbell"]).
- uncertain_fields: list any dot-path field you are not confident about, e.g. \
"exercises.0.sets.1.rpe". Only list fields you actually extracted (not fields you left null).
- Omit fields you cannot determine — do not guess beyond what is written.

Movement-skill conventions (calisthenics, gymnastics rings, juggling, reaction \
drills, shadow boxing, stretching, kettlebell/dumbbell work) — these apply to any \
exercise of these kinds, whether the session is part of a formal program (phase/ \
week given as usual) or unprogrammed:
- If a "Program:" field is stated, always use that instead of inferring. Otherwise, \
if the session has no program name AND no phase/week, it is an ad-hoc session — \
leave program, phase, and week all unset (do not invent a program name). If phase \
and/or week ARE given but no program name is stated, also leave program unset — a \
session with a phase/week is part of a real program whose name just isn't in this \
text (it is usually known from context outside the file, e.g. the file's location).
- Skill-practice runs (e.g. juggling): each run or attempt is one set; the count \
achieved (e.g. catches) is rep_count.full. "3 runs, best 38 catches" with only the \
best stated → one set with full=38 and a note that it was the best of 3 runs.
- Static holds (L-sit, tuck lever, planche leans, stretches held for time): each hold \
is one set with duration_seconds. Do not use the StaticHold failure technique for \
planned holds — it is only for holds performed at failure after an RPE 10 set.
- Timed rounds (shadow boxing, conditioning rounds): each round is one set with \
duration_seconds; include heart_rate_bpm if stated.
- Reaction-time drills: each drill block is one set. If the block is described by a \
count of attempts (e.g. "20 taps"), that count is rep_count.full — it is NOT a \
duration. If the block is described by elapsed time (e.g. "60 second block"), that \
is duration_seconds. Copy measured reaction times verbatim into that set's notes \
(e.g. "avg 245ms, best 198ms"). Never put milliseconds into duration_seconds, \
rep_count, or any numeric field.
- Skill attempts at a specific move (e.g. muscle-up tries, a new transition) are a \
DIFFERENT thing from ordinary reps of an exercise (dips, pull-ups, push-ups) — only \
use this rule when the text explicitly frames the set as attempts at a move, using \
language like "attempts", "tries", or "X clean out of Y". One set per session \
block: rep_count.full = attempts that were completed cleanly, rep_count.partial = \
attempts that were tried but not completed. "5 attempts, 2 clean" → full=2, \
partial=3. Put form detail (which part failed, kip vs strict, band-assisted) in \
notes. Do NOT apply this to ordinary reps whose quality varied across the set (e.g. \
"6 reps, depth dropped on the last two") — every completed rep of a normal exercise \
is rep_count.full regardless of form quality; describe the quality drop-off in \
notes only, never by moving reps into partial."""


class TrainingLogLLMExtract(BaseModel):
    date: str
    program: Optional[str] = None
    phase: Optional[int] = None
    week: Optional[int] = None
    is_deload_week: Optional[bool] = None
    focus: Optional[str] = None
    session_duration_minutes: Optional[int] = None
    warmup: Optional[List[SessionWarmup]] = None
    exercises: List[Exercise]
    cooldown: Optional[List[SessionCooldown]] = None
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


DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


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
