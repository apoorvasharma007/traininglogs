from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel


class SessionSummary(BaseModel):
    session_id: str
    date: date
    program: Optional[str]
    phase: Optional[int]
    week: Optional[int]
    focus: Optional[str]
    duration_minutes: Optional[int]
    is_deload_week: Optional[bool]
    weight_unit: str


class WarmupSetOut(BaseModel):
    number: int
    weight_kg: Optional[float]
    rep_count: Optional[int]
    notes: Optional[str]


class WorkingSetOut(BaseModel):
    number: int
    set_type: str
    weight_kg: Optional[float]
    reps_full: Optional[int]
    reps_partial: Optional[int]
    left_reps_full: Optional[int]
    left_reps_partial: Optional[int]
    right_reps_full: Optional[int]
    right_reps_partial: Optional[int]
    rpe: Optional[float]
    rep_quality: Optional[str]
    rest_minutes: Optional[float]
    rest_seconds: Optional[int]
    duration_seconds: Optional[int]
    distance_meters: Optional[float]
    heart_rate_bpm: Optional[int]
    notes: Optional[str]
    failure_technique: Optional[Any]


class ExerciseOut(BaseModel):
    number: int
    name: str
    exercise_type: str
    notes: Optional[str]
    warmup_notes: Optional[str]
    form_cues: Optional[list[str]]
    goal_weight_kg: Optional[float]
    goal_sets: Optional[int]
    goal_rep_min: Optional[int]
    goal_rep_max: Optional[int]
    goal_rest_min: Optional[int]
    goal_rest_seconds: Optional[int]
    goal_distance_meters: Optional[float]
    goal_target_duration_sec: Optional[int]
    target_muscle_groups: Optional[list[str]]
    rep_tempo: Optional[str]
    sets: list[WorkingSetOut] = []
    warmup_sets: list[WarmupSetOut] = []


class SessionDetail(BaseModel):
    session_id: str
    date: date
    program: Optional[str]
    program_author: Optional[str]
    program_length_weeks: Optional[int]
    phase: Optional[int]
    week: Optional[int]
    is_deload_week: Optional[bool]
    focus: Optional[str]
    duration_minutes: Optional[int]
    weight_unit: str
    user_id: Optional[str]
    user_name: Optional[str]
    exercises: list[ExerciseOut] = []


class ExerciseHistoryRow(BaseModel):
    date: date
    phase: Optional[int]
    week: Optional[int]
    session_id: str
    number: int
    weight_kg: Optional[float]
    reps_full: Optional[int]
    reps_partial: Optional[int]
    rpe: Optional[float]
    rep_quality: Optional[str]
    failure_technique: Optional[Any]
