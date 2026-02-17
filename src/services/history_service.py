"""
History service - provides rich exercise history data.

Services business logic for querying exercise history with insights.
Knows about exercises, not about UI or persistence details.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from repository.data_source import DataSource


@dataclass
class ExerciseOccurrence:
    """Single occurrence of an exercise."""
    name: str
    warmup_sets: List[Dict[str, Any]]
    working_sets: List[Dict[str, Any]]
    session_date: Optional[str]
    days_ago: Optional[int] = None

    def get_max_weight(self) -> Optional[float]:
        """Max weight used in working sets."""
        if not self.working_sets:
            return None
        return max(s.get("weight", 0) for s in self.working_sets)

    def get_avg_rpe(self) -> Optional[float]:
        """Average RPE across working sets."""
        if not self.working_sets:
            return None
        rpes = [s.get("rpe") for s in self.working_sets if s.get("rpe")]
        return sum(rpes) / len(rpes) if rpes else None


class HistoryService:
    """Query exercise history with insights."""

    def __init__(self, data_source: DataSource):
        """
        Initialize history service.
        
        Args:
            data_source: DataSource for querying training data
        """
        self.data_source = data_source

    def get_last_exercise(
        self, 
        exercise_name: str
    ) -> Optional[ExerciseOccurrence]:
        """
        Get the most recent occurrence of an exercise.
        
        Args:
            exercise_name: Name of exercise
            
        Returns:
            ExerciseOccurrence or None if not found
        """
        exercise_data = self.data_source.get_last_exercise(exercise_name)
        if not exercise_data:
            return None

        return self._to_occurrence(exercise_data)

    def get_exercise_progression(
        self,
        exercise_name: str,
        limit: int = 10
    ) -> List[ExerciseOccurrence]:
        """
        Get recent occurrences showing progression.
        
        Args:
            exercise_name: Name of exercise
            limit: Number of recent occurrences
            
        Returns:
            List of ExerciseOccurrence, most recent first
        """
        history = self.data_source.get_exercise_history(exercise_name, limit)
        return [self._to_occurrence(h) for h in history]

    def get_max_weight_achieved(self, exercise_name: str) -> Optional[float]:
        """Get maximum weight ever lifted in exercise."""
        history = self.get_exercise_progression(exercise_name, limit=100)
        if not history:
            return None
        weights = [h.get_max_weight() for h in history if h.get_max_weight() is not None]
        if not weights:
            return None
        return max(weights)

    def get_typical_weight_range(
        self,
        exercise_name: str,
        min_samples: int = 3
    ) -> Optional[tuple]:
        """
        Get typical weight range from history.
        
        Returns:
            (min_weight, avg_weight, max_weight) or None
        """
        history = self.get_exercise_progression(exercise_name, limit=20)
        if len(history) < min_samples:
            return None

        weights = []
        for occurrence in history:
            max_w = occurrence.get_max_weight()
            if max_w:
                weights.append(max_w)

        if not weights:
            return None

        return (min(weights), sum(weights) / len(weights), max(weights))

    def get_typical_rpe_range(
        self,
        exercise_name: str,
        min_samples: int = 3
    ) -> Optional[tuple]:
        """
        Get typical RPE range from history.
        
        Returns:
            (min_rpe, avg_rpe, max_rpe) or None
        """
        history = self.get_exercise_progression(exercise_name, limit=20)
        if len(history) < min_samples:
            return None

        rpes = []
        for occurrence in history:
            avg_rpe = occurrence.get_avg_rpe()
            if avg_rpe:
                rpes.append(avg_rpe)

        if not rpes:
            return None

        return (min(rpes), sum(rpes) / len(rpes), max(rpes))

    def is_new_exercise(self, exercise_name: str) -> bool:
        """Check if this is a new exercise (no history)."""
        return self.get_last_exercise(exercise_name) is None

    def days_since_last_attempt(self, exercise_name: str) -> Optional[int]:
        """Get number of days since last attempt."""
        last = self.get_last_exercise(exercise_name)
        if not last or not last.session_date:
            return None

        try:
            last_date = datetime.fromisoformat(
                last.session_date.replace('Z', '+00:00')
            )
            days = (datetime.now(last_date.tzinfo) - last_date).days
            return max(0, days)
        except (ValueError, TypeError):
            return None

    # Private helpers

    def _to_occurrence(self, exercise_data: Dict[str, Any]) -> ExerciseOccurrence:
        """Convert raw exercise data to ExerciseOccurrence."""
        session_date = exercise_data.get("session_date")
        days_ago = None

        if session_date:
            try:
                date_obj = datetime.fromisoformat(
                    session_date.replace('Z', '+00:00')
                )
                days_ago = (datetime.now(date_obj.tzinfo) - date_obj).days
            except (ValueError, TypeError):
                days_ago = None

        return ExerciseOccurrence(
            name=exercise_data.get("name"),
            warmup_sets=exercise_data.get("warmup_sets", []),
            working_sets=exercise_data.get("working_sets", []),
            session_date=session_date,
            days_ago=days_ago
        )
