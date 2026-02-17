"""
Analytics queries for traininglogs.

Provides read-only analytics on training data.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from persistence import TrainingSessionRepository


class BasicQueries:
    """Read-only analytics queries on training data."""

    def __init__(self, repository: TrainingSessionRepository):
        """
        Initialize BasicQueries.
        
        Args:
            repository: TrainingSessionRepository instance
        """
        self.repository = repository

    def get_last_n_sessions(self, n: int = 5) -> List[Dict[str, Any]]:
        """
        Get last N training sessions.
        
        Args:
            n: Number of sessions
            
        Returns:
            List of session dictionaries
        """
        return self.repository.get_all_sessions(limit=n)

    def get_sessions_in_phase(self, phase: str) -> List[Dict[str, Any]]:
        """
        Get all sessions in a specific phase.
        
        Args:
            phase: Phase name
            
        Returns:
            List of session dictionaries
        """
        return self.repository.get_sessions_by_phase(phase)

    def get_sessions_by_week(self, phase: str, week: int) -> List[Dict[str, Any]]:
        """
        Get sessions for specific phase and week.
        
        Args:
            phase: Phase name
            week: Week number
            
        Returns:
            List of session dictionaries
        """
        return self.repository.get_sessions_by_phase_and_week(phase, week)

    def get_total_volume(self, session: Dict[str, Any]) -> float:
        """
        Calculate total volume (weight × reps) for a session.
        
        Args:
            session: Session dictionary
            
        Returns:
            Total volume in kg-reps
        """
        total = 0.0
        
        for exercise in session.get("exercises", []):
            for working_set in exercise.get("working_sets", []):
                weight = working_set.get("weight_kg", 0)
                full_reps = working_set.get("full_reps", 0)
                partial_reps = working_set.get("partial_reps", 0)
                total_reps = full_reps + partial_reps
                
                total += weight * total_reps
        
        return total

    def get_exercise_volume(self, exercise: Dict[str, Any]) -> float:
        """
        Calculate volume for a single exercise.
        
        Args:
            exercise: Exercise dictionary
            
        Returns:
            Total volume in kg-reps
        """
        total = 0.0
        
        for working_set in exercise.get("working_sets", []):
            weight = working_set.get("weight_kg", 0)
            full_reps = working_set.get("full_reps", 0)
            partial_reps = working_set.get("partial_reps", 0)
            total_reps = full_reps + partial_reps
            
            total += weight * total_reps
        
        return total

    def get_weekly_volume(self, phase: str, week: int) -> Dict[str, Any]:
        """
        Get total volume for a week.
        
        Args:
            phase: Phase name
            week: Week number
            
        Returns:
            Dictionary with total volume and per-exercise breakdown
        """
        sessions = self.get_sessions_by_week(phase, week)
        
        total_volume = 0.0
        exercise_volumes = {}
        
        for session in sessions:
            for exercise in session.get("exercises", []):
                exercise_name = exercise.get("name", "Unknown")
                exercise_vol = self.get_exercise_volume(exercise)
                
                total_volume += exercise_vol
                if exercise_name not in exercise_volumes:
                    exercise_volumes[exercise_name] = 0
                exercise_volumes[exercise_name] += exercise_vol
        
        return {
            "total_volume": total_volume,
            "exercise_volumes": exercise_volumes,
            "session_count": len(sessions)
        }

    def get_exercise_frequency(self, exercise_name: str, phase: Optional[str] = None) -> int:
        """
        Count how many times an exercise appears in sessions.
        
        Args:
            exercise_name: Name of exercise
            phase: Optional phase to filter by
            
        Returns:
            Number of occurrences
        """
        if phase:
            sessions = self.get_sessions_in_phase(phase)
        else:
            sessions = self.repository.get_all_sessions()
        
        count = 0
        for session in sessions:
            for exercise in session.get("exercises", []):
                if exercise.get("name", "").lower() == exercise_name.lower():
                    count += 1
        
        return count

    def show_last_5_sessions(self) -> str:
        """
        Get formatted display of last 5 sessions.
        
        Returns:
            Formatted string
        """
        sessions = self.get_last_n_sessions(5)
        
        if not sessions:
            return "No sessions found."
        
        output = "📊 Last 5 Sessions\n"
        output += "=" * 50 + "\n"
        
        for i, session in enumerate(sessions, 1):
            date = session.get("date", "N/A")
            phase = session.get("phase", "N/A")
            week = session.get("week", "N/A")
            focus = session.get("focus", "N/A")
            exercises = len(session.get("exercises", []))
            volume = self.get_total_volume(session)
            
            output += f"{i}. {date} | {phase} W{week} | {focus}\n"
            output += f"   {exercises} exercises | {volume:.0f}kg-reps\n"
        
        return output

    def show_exercise_history(self, exercise_name: str, limit: int = 5) -> str:
        """
        Get formatted display of exercise history.
        
        Args:
            exercise_name: Name of exercise
            limit: Number of occurrences
            
        Returns:
            Formatted string
        """
        # Simple implementation - get from sessions
        history = []
        all_sessions = self.repository.get_all_sessions()
        
        for session in all_sessions:
            for exercise in session.get("exercises", []):
                if exercise.get("name", "").lower() == exercise_name.lower():
                    history.append({
                        "date": session.get("date"),
                        "exercise": exercise
                    })
                    if len(history) >= limit:
                        break
            if len(history) >= limit:
                break
        
        if not history:
            return f"No history found for: {exercise_name}"
        
        output = f"📚 History: {exercise_name}\n"
        output += "=" * 50 + "\n"
        
        for i, item in enumerate(history, 1):
            date = item["date"]
            working_sets = item["exercise"].get("working_sets", [])
            
            if working_sets:
                last_set = working_sets[-1]
                weight = last_set.get("weight_kg", "N/A")
                full_reps = last_set.get("full_reps", "N/A")
                partial = last_set.get("partial_reps", 0)
                rpe = last_set.get("rpe", "N/A")
                
                output += f"{i}. {date}: {weight}kg × {full_reps}+{partial}p @ RPE {rpe}\n"
        
        return output

    def show_weekly_volume(self, phase: str, week: int) -> str:
        """
        Get formatted display of weekly volume.
        
        Args:
            phase: Phase name
            week: Week number
            
        Returns:
            Formatted string
        """
        data = self.get_weekly_volume(phase, week)
        
        output = f"📊 Volume: {phase} Week {week}\n"
        output += "=" * 50 + "\n"
        output += f"Total Volume: {data['total_volume']:.0f} kg-reps\n"
        output += f"Sessions: {data['session_count']}\n"
        
        if data['exercise_volumes']:
            output += "\nExercise Breakdown:\n"
            for exercise, volume in sorted(
                data['exercise_volumes'].items(), 
                key=lambda x: x[1], 
                reverse=True
            ):
                output += f"  {exercise}: {volume:.0f} kg-reps\n"
        
        return output
