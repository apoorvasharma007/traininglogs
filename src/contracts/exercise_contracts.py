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
    warmup_sets: List[Dict[str, Any]] = field(default_factory=list)
    working_sets: List[Dict[str, Any]] = field(default_factory=list)
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "warmup_sets": self.warmup_sets,
            "working_sets": self.working_sets,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ExerciseContract:
    """Committed exercise payload contract."""

    name: str
    warmup_sets: List[Dict[str, Any]]
    working_sets: List[Dict[str, Any]]
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "warmup_sets": self.warmup_sets,
            "working_sets": self.working_sets,
            "notes": self.notes,
        }

