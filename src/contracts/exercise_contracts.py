"""Contracts for exercise and set data mapped from user input."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class SetContract:
    """Canonical representation of one set."""

    weight: float
    reps: int
    rpe: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        set_data: Dict[str, Any] = {"weight": self.weight, "reps": self.reps}
        if self.rpe is not None:
            set_data["rpe"] = self.rpe
        return set_data


@dataclass
class ExerciseDraftContract:
    """Mutable draft state for one in-progress exercise."""

    name: str
    goal: Optional[Dict[str, Any]] = None
    rest_minutes: Optional[int] = None
    tempo: Optional[str] = None
    muscles: Optional[List[str]] = None
    warmup_notes: Optional[str] = None
    cues: List[str] = field(default_factory=list)
    warmup_sets: List[Dict[str, Any]] = field(default_factory=list)
    working_sets: List[Dict[str, Any]] = field(default_factory=list)
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        draft = {
            "name": self.name,
            "goal": self.goal,
            "rest_minutes": self.rest_minutes,
            "tempo": self.tempo,
            "muscles": self.muscles,
            "warmup_notes": self.warmup_notes,
            "cues": self.cues,
            "warmup_sets": self.warmup_sets,
            "working_sets": self.working_sets,
            "notes": self.notes,
        }
        return {k: v for k, v in draft.items() if v not in (None, [])}


@dataclass(frozen=True)
class ExerciseContract:
    """Committed exercise payload contract."""

    name: str
    goal: Optional[Dict[str, Any]]
    rest_minutes: Optional[int]
    tempo: Optional[str]
    muscles: Optional[List[str]]
    warmup_notes: Optional[str]
    cues: List[str]
    warmup_sets: List[Dict[str, Any]]
    working_sets: List[Dict[str, Any]]
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "name": self.name,
            "goal": self.goal,
            "rest_minutes": self.rest_minutes,
            "tempo": self.tempo,
            "muscles": self.muscles,
            "warmup_notes": self.warmup_notes,
            "cues": self.cues,
            "warmup_sets": self.warmup_sets,
            "working_sets": self.working_sets,
            "notes": self.notes,
        }
        return {k: v for k, v in payload.items() if v not in (None, [])}
