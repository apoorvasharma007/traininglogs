"""
Exercise history service for traininglogs.

Retrieves previous exercise data for reference during logging.
"""

from typing import Optional, Dict, Any
from persistence import TrainingSessionRepository


class HistoryService:
    """Service for retrieving exercise history."""

    def __init__(self, repository: TrainingSessionRepository):
        """
        Initialize HistoryService.
        
        Args:
            repository: TrainingSessionRepository instance
        """
        self.repository = repository

    def get_last_exercise(self, exercise_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent occurrence of a specific exercise.
        
        Args:
            exercise_name: Name of the exercise
            
        Returns:
            Exercise data or None if not found
        """
        try:
            return self.repository.get_last_occurrence_of_exercise(exercise_name)
        except Exception:
            return None

    def get_last_n_sessions(self, n: int = 5) -> list:
        """
        Get last N training sessions.
        
        Args:
            n: Number of sessions to retrieve
            
        Returns:
            List of session dictionaries
        """
        try:
            return self.repository.get_all_sessions(limit=n)
        except Exception:
            return []

    def get_exercise_history(self, exercise_name: str, limit: int = 10) -> list:
        """
        Get history of a specific exercise across all sessions.
        
        Args:
            exercise_name: Name of the exercise
            limit: Maximum number of occurrences to retrieve
            
        Returns:
            List of exercise data dictionaries
        """
        history = []
        
        try:
            sessions = self.repository.get_all_sessions(limit=50)
            
            for session in sessions:
                exercises = session.get("exercises", [])
                for exercise in exercises:
                    if exercise.get("name", "").lower() == exercise_name.lower():
                        history.append({
                            "session_id": session.get("id"),
                            "date": session.get("date"),
                            "phase": session.get("phase"),
                            "week": session.get("week"),
                            "exercise": exercise
                        })
                        
                        if len(history) >= limit:
                            return history
        except Exception:
            pass
        
        return history

    def get_last_weight_and_reps(self, exercise_name: str) -> Optional[Dict[str, Any]]:
        """
        Get weight and reps from last occurrence of exercise.
        
        Args:
            exercise_name: Name of the exercise
            
        Returns:
            Dictionary with weight_kg and reps info, or None
        """
        last_exercise = self.get_last_exercise(exercise_name)
        
        if not last_exercise:
            return None
        
        working_sets = last_exercise.get("working_sets", [])
        if not working_sets:
            return None
        
        # Get last working set
        last_set = working_sets[-1]
        
        return {
            "weight_kg": last_set.get("weight_kg"),
            "full_reps": last_set.get("full_reps"),
            "partial_reps": last_set.get("partial_reps", 0),
            "rpe": last_set.get("rpe"),
            "rep_quality": last_set.get("rep_quality")
        }

    def get_average_weight(self, exercise_name: str, limit: int = 10) -> Optional[float]:
        """
        Get average weight for an exercise across recent sessions.
        
        Args:
            exercise_name: Name of the exercise
            limit: Number of recent sessions to consider
            
        Returns:
            Average weight in kg, or None if no data
        """
        history = self.get_exercise_history(exercise_name, limit=limit)
        
        if not history:
            return None
        
        weights = []
        for item in history:
            working_sets = item["exercise"].get("working_sets", [])
            if working_sets:
                last_set = working_sets[-1]
                weight = last_set.get("weight_kg")
                if weight is not None:
                    weights.append(float(weight))
        
        if not weights:
            return None
        
        return sum(weights) / len(weights)

    def get_exercise_progression(self, exercise_name: str, limit: int = 10) -> list:
        """
        Get progression data for an exercise.
        
        Args:
            exercise_name: Name of the exercise
            limit: Number of recent occurrences
            
        Returns:
            List of progression data with weight, reps, date
        """
        history = self.get_exercise_history(exercise_name, limit=limit)
        
        progression = []
        for item in history:
            working_sets = item["exercise"].get("working_sets", [])
            if working_sets:
                last_set = working_sets[-1]
                progression.append({
                    "date": item["date"],
                    "weight_kg": last_set.get("weight_kg"),
                    "full_reps": last_set.get("full_reps"),
                    "partial_reps": last_set.get("partial_reps", 0),
                    "rpe": last_set.get("rpe"),
                    "total_reps": (last_set.get("full_reps", 0) + 
                                   last_set.get("partial_reps", 0))
                })
        
        return progression
