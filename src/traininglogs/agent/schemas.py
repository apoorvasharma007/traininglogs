from __future__ import annotations

import datetime
import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from traininglogs.models.models import Exercise, SessionCooldown, SessionWarmup


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


class ExerciseExtract(BaseModel):
    """One worker call's result: a single Exercise plus the uncertain_fields that apply to
    it. Dot-paths are relative to the exercise (e.g. "sets.1.rpe"), not the full session."""

    exercise: Exercise
    uncertain_fields: List[str] = Field(default_factory=list)


class ExercisePosition(BaseModel):
    """One entry in the splitter's ordered exercise listing."""

    position: int
    name: str

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


class ExerciseSplit(BaseModel):
    """The splitter call's result: how many exercises the session has, and their names, in
    order. Workers are told "extract the Nth exercise" using this list's positions."""

    exercises: List[ExercisePosition]


class LLMParserError(Exception):
    pass
