from __future__ import annotations

import re
import datetime
from enum import Enum
from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

MAX_REST_INTERVAL_MINUTES = 15
MAX_REST_INTERVAL_SECONDS = 900


class RepCount(BaseModel):
    full: int
    partial: int = 0

    @field_validator("full")
    @classmethod
    def full_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Full reps cannot be negative")
        return v

    @field_validator("partial", mode="before")
    @classmethod
    def coerce_partial_none(cls, v: object) -> int:
        return 0 if v is None else v

    @field_validator("partial")
    @classmethod
    def partial_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Partial reps cannot be negative")
        return v

    @property
    def total_reps(self) -> int:
        return self.full + self.partial


class RepRange(BaseModel):
    min: int
    max: int

    @model_validator(mode="after")
    def valid_range(self) -> RepRange:
        if self.min <= 0:
            raise ValueError("Minimum reps must be positive")
        if self.max <= 0:
            raise ValueError("Maximum reps must be positive")
        if self.min > self.max:
            raise ValueError("Minimum reps cannot be greater than maximum reps")
        return self


class Rest(BaseModel):
    minutes: Optional[int] = None
    seconds: Optional[int] = None

    @field_validator("minutes")
    @classmethod
    def minutes_in_range(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > MAX_REST_INTERVAL_MINUTES):
            raise ValueError(f"rest minutes must be between 0 and {MAX_REST_INTERVAL_MINUTES}")
        return v

    @field_validator("seconds")
    @classmethod
    def seconds_in_range(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > MAX_REST_INTERVAL_SECONDS):
            raise ValueError(f"rest seconds must be between 0 and {MAX_REST_INTERVAL_SECONDS}")
        return v

    @model_validator(mode="after")
    def not_both_set(self) -> Rest:
        if self.minutes is not None and self.seconds is not None:
            raise ValueError("rest cannot have both minutes and seconds set simultaneously")
        return self


class UnilateralReps(BaseModel):
    left: Optional[RepCount] = None
    right: Optional[RepCount] = None


class Goal(BaseModel):
    weight_kg: Optional[float] = None
    sets: Optional[int] = None
    rep_range: Optional[RepRange] = None
    rest: Optional[Rest] = None
    distance_meters: Optional[float] = None
    target_duration_seconds: Optional[int] = None

    @field_validator("weight_kg")
    @classmethod
    def weight_non_negative(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("Weight must be positive or zero for bodyweight")
        return v

    @field_validator("sets")
    @classmethod
    def sets_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("Number of sets must be positive")
        return v

    @field_validator("distance_meters")
    @classmethod
    def distance_non_negative(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("distance_meters must be non-negative")
        return v

    @field_validator("target_duration_seconds")
    @classmethod
    def target_duration_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("target_duration_seconds must be positive")
        return v


class RepQualityAssessment(str, Enum):
    GOOD = "good"
    BAD = "bad"
    PERFECT = "perfect"
    LEARNING = "learning"


class MyoRep(BaseModel):
    number: int
    rep_count: RepCount

    @field_validator("number")
    @classmethod
    def number_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("MyoRep.number must be a positive integer")
        return v


class MyoRepDetails(BaseModel):
    mini_sets: List[MyoRep]


class LLPDetails(BaseModel):
    partial_rep_count: int

    @field_validator("partial_rep_count")
    @classmethod
    def count_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("partial_rep_count cannot be negative")
        return v


class StaticDetails(BaseModel):
    hold_duration_seconds: int

    @field_validator("hold_duration_seconds")
    @classmethod
    def duration_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("hold_duration_seconds must be positive")
        return v


class DropSet(BaseModel):
    number: int
    weight_kg: float
    rep_count: RepCount

    @field_validator("number")
    @classmethod
    def number_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("DropSet.number must be a positive integer")
        return v

    @field_validator("weight_kg")
    @classmethod
    def weight_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("DropSet.weight_kg must be a non-negative number")
        return v


class DropSetDetails(BaseModel):
    drop_sets: List[DropSet]


class MyoRepsTechnique(BaseModel):
    technique_type: Literal["MyoReps"]
    details: MyoRepDetails


class LLPTechnique(BaseModel):
    technique_type: Literal["LLP"]
    details: LLPDetails


class StaticTechnique(BaseModel):
    technique_type: Literal["StaticHold"]
    details: StaticDetails


class DropSetTechnique(BaseModel):
    technique_type: Literal["DropSet"]
    details: DropSetDetails


FailureTechnique = Annotated[
    Union[MyoRepsTechnique, LLPTechnique, StaticTechnique, DropSetTechnique],
    Field(discriminator="technique_type"),
]


class WarmupSet(BaseModel):
    number: int
    weight_kg: float
    rep_count: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("number")
    @classmethod
    def number_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Set number must be positive")
        return v

    @field_validator("weight_kg")
    @classmethod
    def weight_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Weight must be positive or zero for bodyweight")
        return v

    @field_validator("rep_count")
    @classmethod
    def rep_count_non_negative(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Rep count cannot be negative")
        return v


def _validate_rpe(v: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError("RPE must be a number")
    if not (1.0 <= v <= 10.0):
        raise ValueError("RPE must be between 1 and 10")
    frac = v - int(v)
    if abs(frac) > 1e-9 and abs(frac - 0.5) > 1e-9:
        raise ValueError("RPE must be a whole number or half-step (e.g. 7 or 7.5)")
    return v


class WorkingSet(BaseModel):
    number: int
    rpe: Optional[float] = None
    rest: Optional[Rest] = None
    notes: Optional[str] = None
    weight_kg: Optional[float] = None
    rep_count: Optional[RepCount] = None
    unilateral_rep_count: Optional[UnilateralReps] = None
    rep_quality_assessment: Optional[RepQualityAssessment] = None
    failure_technique: Optional[FailureTechnique] = None
    duration_seconds: Optional[int] = None
    distance_meters: Optional[float] = None
    heart_rate_bpm: Optional[int] = None

    @field_validator("number")
    @classmethod
    def number_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Set number must be positive")
        return v

    @field_validator("rpe")
    @classmethod
    def validate_rpe(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            _validate_rpe(v)
        return v

    @field_validator("weight_kg")
    @classmethod
    def weight_non_negative(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("Weight must be positive or zero for bodyweight")
        return v

    @field_validator("duration_seconds")
    @classmethod
    def duration_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("duration_seconds must be positive")
        return v

    @field_validator("distance_meters")
    @classmethod
    def distance_non_negative(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("distance_meters must be non-negative")
        return v

    @field_validator("heart_rate_bpm")
    @classmethod
    def heart_rate_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("heart_rate_bpm must be positive")
        return v

    @model_validator(mode="after")
    def failure_technique_requires_rpe_10(self) -> WorkingSet:
        if self.failure_technique is not None and (self.rpe is None or self.rpe != 10):
            raise ValueError("Failure technique can only be used with RPE 10 sets")
        return self


class SessionWarmup(BaseModel):
    number: int
    name: str
    reps: Optional[int] = None
    duration_seconds: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("number")
    @classmethod
    def number_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("number must be positive")
        return v

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name cannot be empty")
        return v

    @field_validator("reps")
    @classmethod
    def reps_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("reps must be positive")
        return v

    @field_validator("duration_seconds")
    @classmethod
    def duration_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("duration_seconds must be positive")
        return v


class SessionCooldown(BaseModel):
    number: int
    name: str
    reps: Optional[int] = None
    duration_seconds: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("number")
    @classmethod
    def number_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("number must be positive")
        return v

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name cannot be empty")
        return v

    @field_validator("reps")
    @classmethod
    def reps_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("reps must be positive")
        return v

    @field_validator("duration_seconds")
    @classmethod
    def duration_positive(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("duration_seconds must be positive")
        return v


class Exercise(BaseModel):
    number: int
    name: str
    tags: Optional[List[str]] = None
    modality: Optional[str] = None
    movement_pattern: Optional[List[str]] = None
    sets: Optional[List[WorkingSet]] = None
    target_muscle_groups: Optional[List[str]] = None
    rep_tempo: Optional[str] = None
    current_goal: Optional[Goal] = None
    warmup_sets: Optional[List[WarmupSet]] = None
    notes: Optional[str] = None
    warmup_notes: Optional[str] = None
    form_cues: Optional[List[str]] = None

    @field_validator("number")
    @classmethod
    def number_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Exercise number must be positive")
        return v

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Exercise name cannot be empty")
        return v

    @field_validator("warmup_sets", mode="before")
    @classmethod
    def filter_null_warmup_sets(cls, v: object) -> object:
        if isinstance(v, list):
            return [x for x in v if x is not None]
        return v


class TrainingSession(BaseModel):
    data_model_version: str
    data_model_type: str
    session_id: str
    user_id: str
    user_name: str
    date: str
    program: Optional[str] = None
    program_author: Optional[str] = None
    program_length_weeks: Optional[int] = None
    phase: Optional[int] = None
    week: Optional[int] = None
    is_deload_week: Optional[bool] = None
    focus: Optional[str] = None
    warmup: Optional[List[SessionWarmup]] = None
    exercises: List[Exercise]
    cooldown: Optional[List[SessionCooldown]] = None
    session_duration_minutes: Optional[int] = None
    weight_unit: Literal["kg", "lbs"] = "kg"

    @field_validator(
        "data_model_version", "data_model_type", "session_id", "user_id",
        "user_name",
    )
    @classmethod
    def not_empty_string(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("cannot be empty")
        return v

    @field_validator("program", "program_author", "focus")
    @classmethod
    def not_empty_string_if_set(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("cannot be empty")
        return v

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

    @field_validator("program_length_weeks", "phase", "session_duration_minutes")
    @classmethod
    def positive_int(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
                raise ValueError("must be a positive integer")
        return v

    @model_validator(mode="after")
    def validate_session(self) -> TrainingSession:
        if self.week is not None and self.program_length_weeks is not None:
            if not (1 <= self.week <= self.program_length_weeks):
                raise ValueError(
                    f"week must be between 1 and {self.program_length_weeks}, got {self.week}"
                )
        for i, exercise in enumerate(self.exercises):
            if exercise.number != i + 1:
                raise ValueError(
                    f"Exercise number must be sequential, expected {i + 1}, got {exercise.number}"
                )
        for i, movement in enumerate(self.warmup or []):
            if movement.number != i + 1:
                raise ValueError(
                    f"Warmup number must be sequential, expected {i + 1}, got {movement.number}"
                )
        for i, movement in enumerate(self.cooldown or []):
            if movement.number != i + 1:
                raise ValueError(
                    f"Cooldown number must be sequential, expected {i + 1}, got {movement.number}"
                )
        return self

    def get_exercise_by_name(self, name: str) -> Optional[Exercise]:
        target = (name or "").strip().lower()
        for exercise in self.exercises:
            if (exercise.name or "").strip().lower() == target:
                return exercise
        return None
