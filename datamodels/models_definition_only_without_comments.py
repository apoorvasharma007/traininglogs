# dataclasses_definitions.py
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Union
from enum import Enum

@dataclass
class RepCount:
    full: int
    partial: int = 0

@dataclass
class RepRange:
    min: int
    max: int

@dataclass
class Goal:
    weight_kg: float
    sets: int
    rep_range: RepRange
    rest_minutes: int

class FailureTechniqueType(Enum):
    MYO_REPS = "MyoReps"
    LLP = "LLP"
    STATIC = "StaticHold"
    DROP_SET = "DropSet"

class RepQualityAssessment(Enum):
    GOOD = "good"
    BAD = "bad"
    PERFECT = "perfect"
    LEARNING = "learning"

@dataclass
class MyoRepDetails:
    mini_sets: List[Dict[str, RepCount]]

@dataclass
class LLPDetails:
    partial_rep_count: int

@dataclass
class StaticDetails:
    hold_duration_seconds: int

@dataclass
class DropSet:
    number: int
    weight_kg: float
    rep_count: RepCount

@dataclass
class DropSetDetails:
    entries: List[DropSet]

FailureDetails = Union[MyoRepDetails, LLPDetails, StaticDetails, DropSetDetails]

@dataclass
class FailureTechnique:
    technique_type: FailureTechniqueType
    details: FailureDetails

@dataclass
class WarmupSet:
    number: int
    weight_kg: float
    rep_count: Optional[int] = None
    notes: Optional[str] = None

@dataclass
class WorkingSet:
    number: int
    weight_kg: float
    rep_count: RepCount
    rpe: Optional[float] = None
    rep_quality_assessment: Optional[RepQualityAssessment] = None
    actual_rest_minutes: Optional[int] = None
    notes: Optional[str] = None
    failure_technique: Optional[FailureTechnique] = None

@dataclass
class Exercise:
    number: int
    name: str
    working_sets: List[WorkingSet] = field(default_factory=list)
    target_muscle_groups: Optional[List[str]] = None
    rep_tempo: Optional[str] = None
    current_goal: Optional[Goal] = None
    warmup_sets: Optional[List[WarmupSet]] = None
    notes: Optional[str] = None
    warmup_notes: Optional[str] = None
    form_cues: Optional[List[str]] = None

@dataclass
class TrainingSession:
    data_model_version: str
    data_model_type: str
    session_id: str
    user_id: str
    user_name: str
    date: str
    phase: int
    week: int
    is_deload_week: bool
    focus: str
    exercises: List[Exercise]
    session_duration_minutes: int