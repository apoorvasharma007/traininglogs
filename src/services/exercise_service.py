"""
Exercise service - builds exercises programmatically.

Pure business logic for exercise creation and validation.
Zero UI coupling - can be used in CLI, API, batch processing, etc.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from core.validators import Validators, ValidationError


@dataclass
class Exercise:
    """Exercise with all sets and metadata."""
    name: str
    warmup_sets: List[Dict[str, Any]]
    working_sets: List[Dict[str, Any]]
    notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "name": self.name,
            "warmup_sets": self.warmup_sets,
            "working_sets": self.working_sets,
            "notes": self.notes
        }


class ExerciseService:
    """Build and validate exercises."""

    def __init__(self):
        """Initialize exercise service."""
        self.validators = Validators()

    def build_exercise(
        self,
        name: str,
        warmup_sets: Optional[List[Dict[str, Any]]] = None,
        working_sets: Optional[List[Dict[str, Any]]] = None,
        notes: Optional[str] = None
    ) -> Exercise:
        """
        Build an exercise from components.
        
        Args:
            name: Exercise name
            warmup_sets: List of warmup sets
            working_sets: List of working sets
            notes: Optional notes
            
        Returns:
            Exercise object
            
        Raises:
            ValidationError: If exercise is invalid
        """
        exercise = Exercise(
            name=name,
            warmup_sets=warmup_sets or [],
            working_sets=working_sets or [],
            notes=notes
        )
        
        self.validate_exercise(exercise)
        return exercise

    def validate_exercise(self, exercise: Exercise) -> bool:
        """
        Validate exercise completeness.
        
        Args:
            exercise: Exercise to validate
            
        Returns:
            True if valid
            
        Raises:
            ValidationError: If invalid
        """
        errors = []

        # Name validation
        if not exercise.name or not exercise.name.strip():
            errors.append("Exercise name required")
        elif len(exercise.name) < 2:
            errors.append("Exercise name too short")

        # Sets validation
        if not exercise.working_sets:
            errors.append("At least one working set required")

        # Per-set validation
        for idx, set_data in enumerate(exercise.working_sets, 1):
            try:
                self._validate_set(set_data, f"Working set {idx}")
            except ValidationError as e:
                errors.append(f"Working set {idx}: {str(e)}")

        # Warmups are optional, but validate if present
        for idx, set_data in enumerate(exercise.warmup_sets, 1):
            try:
                self._validate_set(set_data, f"Warmup {idx}", is_warmup=True)
            except ValidationError as e:
                errors.append(f"Warmup {idx}: {str(e)}")

        if errors:
            raise ValidationError("; ".join(errors))

        return True

    def get_exercise_summary(self, exercise: Exercise) -> str:
        """
        Get human-readable summary of exercise.
        
        Args:
            exercise: Exercise to summarize
            
        Returns:
            Summary string
        """
        warmup_count = len(exercise.warmup_sets)
        working_count = len(exercise.working_sets)

        summary = f"{exercise.name}"

        if warmup_count > 0:
            summary += f" | {warmup_count} warmup"

        working_str = " | ".join([
            self._set_to_string(s)
            for s in exercise.working_sets
        ])
        summary += f" | {working_str}"

        return summary

    def estimate_rpe(
        self,
        weight: float,
        reps: int,
        max_weight: Optional[float] = None
    ) -> Optional[int]:
        """
        Estimate RPE based on weight and reps.
        
        Simple heuristic: if weight is close to max and doing low reps, high RPE.
        
        Args:
            weight: Weight lifted
            reps: Reps achieved
            max_weight: Max weight ever achieved (for context)
            
        Returns:
            Estimated RPE (1-10) or None if can't estimate
        """
        if reps <= 0 or weight <= 0:
            return None

        # Simple heuristic: more reps = lower RPE for same weight
        if reps >= 10:
            return 6  # Many reps typically feels easier
        elif reps >= 8:
            return 7
        elif reps >= 5:
            return 8
        else:
            return 9  # Low reps, typically harder

        return None

    # Private helpers

    def _validate_set(
        self,
        set_data: Dict[str, Any],
        set_label: str,
        is_warmup: bool = False
    ) -> bool:
        """Validate individual set."""
        errors = []

        weight = set_data.get("weight")
        reps = set_data.get("reps")

        if weight is None or weight < 0:
            errors.append(f"{set_label}: Weight required and must be >= 0")

        if reps is None or reps < 1:
            errors.append(f"{set_label}: Reps required and must be >= 1")

        if is_warmup and reps > 20:
            errors.append(f"{set_label}: Warmup reps typically <= 20")
        elif not is_warmup and reps > 50:
            errors.append(f"{set_label}: Working reps unusually high")

        if weight > 500:  # Sanity check
            errors.append(f"{set_label}: Weight seems unreasonably high")

        if errors:
            raise ValidationError("; ".join(errors))

        return True

    def _set_to_string(self, set_data: Dict[str, Any]) -> str:
        """Convert set to display string."""
        weight = set_data.get("weight", 0)
        reps = set_data.get("reps", 0)
        rpe = set_data.get("rpe")

        s = f"{weight}kg × {reps}"
        if rpe:
            s += f" @ RPE {rpe}"

        return s
