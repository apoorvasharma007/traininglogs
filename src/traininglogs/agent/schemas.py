from __future__ import annotations

import datetime
import re
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from traininglogs.models.models import Exercise, Goal, SessionCooldown, SessionWarmup


def _validate_date(v: str) -> str:
    if not isinstance(v, str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
        raise ValueError("Date must be formatted as YYYY-MM-DD")
    try:
        datetime.datetime.strptime(v, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Date is not a valid calendar date: {v}")
    return v


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
    notes: Optional[str] = None
    uncertain_fields: List[str] = Field(default_factory=list)
    # Deterministic drop-check findings (exercise-count mismatch, orphaned RPE/weight-shaped
    # tokens) — distinct from uncertain_fields, which is the LLM's own self-reported doubt
    # about a field it did extract. A warning means "we think this is actually wrong."
    warnings: List[str] = Field(default_factory=list)

    @field_validator("date")
    @classmethod
    def valid_date(cls, v: str) -> str:
        return _validate_date(v)


class SessionShellExtract(BaseModel):
    """Everything a TrainingLogLLMExtract has except `exercises` — the session-level call
    in the split extraction flow. A separate call per exercise fills in `exercises`."""

    date: str
    program: Optional[str] = None
    phase: Optional[int] = None
    week: Optional[int] = None
    is_deload_week: Optional[bool] = None
    focus: Optional[str] = None
    session_duration_minutes: Optional[int] = None
    warmup: Optional[List[SessionWarmup]] = None
    cooldown: Optional[List[SessionCooldown]] = None
    notes: Optional[str] = None
    uncertain_fields: List[str] = Field(default_factory=list)

    @field_validator("date")
    @classmethod
    def valid_date(cls, v: str) -> str:
        return _validate_date(v)


class ExerciseExtract(Exercise):
    """One worker call's result: Exercise's own fields, flattened at the top level, plus
    uncertain_fields. Deliberately NOT `exercise: Exercise` nested under a wrapper key — live
    testing showed tool-calling models reliably flatten a single-nested-object schema
    regardless of prompt wording (Groq/llama-3.3-70b did this on the first live run: it
    produced every field correctly, just not wrapped). Matching that tendency is more robust
    than fighting it with prompt engineering. Dot-paths in uncertain_fields are relative to
    the exercise (e.g. "sets.1.rpe"), not the full session. extraction.assemble() converts
    this back to a plain Exercise before it goes anywhere near the rest of the pipeline."""

    uncertain_fields: List[str] = Field(default_factory=list)


class ExerciseLabelsExtract(BaseModel):
    """One narrow-path worker call's result — used only when parse_exercise_block() (see
    extraction.py) already supplied this exercise's numeric spine (sets, warmup_sets)
    deterministically. Deliberately has no sets/warmup_sets fields at all: the LLM is
    structurally never asked for them on this path, so it cannot get them wrong the way the
    full ExerciseExtract path can.

    set_notes keys must be among the set numbers the caller supplied in its prompt (the
    parser's own set numbers); the caller drops any key that isn't, with a warning, rather than
    treating it as fatal. exercise_rpe_target_set is only meaningful when the parser found an
    exercise-level RPE mentioned once for the whole exercise (ParsedBlock.exercise_rpe) — this
    field says which of the given set numbers that RPE belongs to. The RPE *value* is always
    deterministic (the parser read it); only its *placement* is still a judgment call, same as
    the full-extraction path's last-set convention."""

    name: str
    tags: Optional[List[str]] = None
    modality: Optional[str] = None
    movement_pattern: Optional[List[str]] = None
    target_muscle_groups: Optional[List[str]] = None
    rep_tempo: Optional[str] = None
    current_goal: Optional[Goal] = None
    notes: Optional[str] = None
    warmup_notes: Optional[str] = None
    form_cues: Optional[List[str]] = None
    set_notes: Dict[str, str] = Field(default_factory=dict)
    exercise_rpe_target_set: Optional[int] = None
    uncertain_fields: List[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Exercise name cannot be empty")
        return v


class ExercisePosition(BaseModel):
    """One entry in the splitter's ordered exercise listing. `anchor` is a verbatim quote used
    to deterministically locate this exercise's text in the source document (see
    extraction._chunk_exercises) — deliberately separate from `name`, which is the cleaned,
    canonical label and is NOT guaranteed to appear literally in the source text."""

    position: int
    name: str
    anchor: str

    @field_validator("position")
    @classmethod
    def position_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Position must be positive")
        return v

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Exercise name cannot be empty")
        return v

    @field_validator("anchor")
    @classmethod
    def anchor_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Anchor cannot be empty")
        return v


class ExerciseSplit(BaseModel):
    """The splitter call's result: how many exercises the session has, and their names, in
    order. Workers are told "extract the Nth exercise" using this list's positions."""

    exercises: List[ExercisePosition]


class LLMParserError(Exception):
    pass
