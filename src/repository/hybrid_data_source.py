"""
Hybrid data source combining database and JSON files.

Queries both SQLite and JSON files, providing transparent access
to all training data regardless of storage location.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from repository.data_source import DataSource


class HybridDataSource(DataSource):
    """Data source combining database and JSON files."""

    def __init__(self, db_repo, json_dir: str = "data/output/sessions"):
        """
        Initialize hybrid data source.
        
        Args:
            db_repo: TrainingSessionRepository for database access
            json_dir: Directory containing JSON session files
        """
        self.db = db_repo
        self.json_dir = Path(json_dir)
        self._exercises_cache = {}

    def get_last_exercise(self, exercise_name: str) -> Optional[Dict[str, Any]]:
        """
        Get most recent occurrence of exercise.
        
        Queries database first (faster), falls back to JSON files.
        """
        # Try database first (faster)
        sessions = self.db.get_all_sessions()
        for session in reversed(sessions):  # Most recent first
            for exercise in session.get("exercises", []):
                if exercise.get("name", "").lower() == exercise_name.lower():
                    return self._normalize_exercise(exercise, session.get("date"))

        # Fall back to JSON files if not found
        return self._get_last_exercise_from_json(exercise_name)

    def get_exercise_history(
        self, 
        exercise_name: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent occurrences of an exercise."""
        history = []

        # Get from database
        sessions = self.db.get_all_sessions()
        for session in reversed(sessions):
            for exercise in session.get("exercises", []):
                if exercise.get("name", "").lower() == exercise_name.lower():
                    history.append(
                        self._normalize_exercise(exercise, session.get("date"))
                    )
                    if len(history) >= limit:
                        return history

        # Supplement from JSON if needed
        if len(history) < limit:
            json_history = self._get_exercise_history_from_json(
                exercise_name, 
                limit - len(history)
            )
            history.extend(json_history)

        return history[:limit]

    def get_sessions(
        self,
        phase: Optional[str] = None,
        week: Optional[int] = None,
        focus: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Query sessions with optional filters."""
        sessions = []

        # Get from database
        all_sessions = self.db.get_all_sessions()
        for session in reversed(all_sessions):
            if self._matches_filters(session, phase, week, focus):
                sessions.append(session)
                if len(sessions) >= limit:
                    return sessions

        # Supplement from JSON if needed
        if len(sessions) < limit:
            json_sessions = self._get_sessions_from_json(
                phase, week, focus, limit - len(sessions)
            )
            sessions.extend(json_sessions)

        return sessions[:limit]

    def save_session(self, session_data: Dict[str, Any]) -> bool:
        """Save session to database and JSON."""
        session_id = session_data.get("id")
        try:
            # Save to database
            self.db.save_session(session_id, session_data)

            # Also save to JSON (handled by SessionManager's exporter)
            # but accessible here if needed
            return True
        except Exception as e:
            raise Exception(f"Failed to save session: {e}")

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve specific session."""
        # Try database first
        all_sessions = self.db.get_all_sessions()
        for session in all_sessions:
            if session.get("id") == session_id:
                return session

        # Try JSON files
        return self._get_session_from_json(session_id)

    def search_exercises(
        self,
        pattern: str,
        limit: int = 5
    ) -> List[str]:
        """Search for exercises by name pattern."""
        exercises_found = set()

        # Search database
        sessions = self.db.get_all_sessions()
        for session in sessions:
            for exercise in session.get("exercises", []):
                name = exercise.get("name", "")
                if pattern.lower() in name.lower():
                    exercises_found.add(name)
                    if len(exercises_found) >= limit:
                        return sorted(list(exercises_found))

        # Search JSON files
        json_exercises = self._search_exercises_in_json(pattern, limit)
        exercises_found.update(json_exercises)

        return sorted(list(exercises_found))[:limit]

    # Helper methods

    def _normalize_exercise(
        self, 
        exercise: Dict[str, Any], 
        session_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Normalize exercise data from different sources."""
        return {
            "name": exercise.get("name"),
            "warmup_sets": exercise.get("warmup_sets", []),
            "working_sets": exercise.get("working_sets", []),
            "session_date": session_date
        }

    def _matches_filters(
        self,
        session: Dict[str, Any],
        phase: Optional[str],
        week: Optional[int],
        focus: Optional[str]
    ) -> bool:
        """Check if session matches filters."""
        if phase and session.get("phase") != phase:
            return False
        if week and session.get("week") != week:
            return False
        if focus and session.get("focus") != focus:
            return False
        return True

    def _get_last_exercise_from_json(
        self, 
        exercise_name: str
    ) -> Optional[Dict[str, Any]]:
        """Query JSON files for exercise."""
        if not self.json_dir.exists():
            return None

        for json_file in sorted(self.json_dir.glob("*.json"), reverse=True):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                for exercise in data.get("exercises", []):
                    if exercise.get("Name", "").lower() == exercise_name.lower():
                        return self._normalize_exercise(
                            exercise, 
                            data.get("date")
                        )
            except json.JSONDecodeError:
                continue

        return None

    def _get_exercise_history_from_json(
        self,
        exercise_name: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Get exercise history from JSON files."""
        history = []
        if not self.json_dir.exists():
            return history

        for json_file in sorted(self.json_dir.glob("*.json"), reverse=True):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                for exercise in data.get("exercises", []):
                    if exercise.get("Name", "").lower() == exercise_name.lower():
                        history.append(
                            self._normalize_exercise(exercise, data.get("date"))
                        )
                        if len(history) >= limit:
                            return history
            except json.JSONDecodeError:
                continue

        return history

    def _get_sessions_from_json(
        self,
        phase: Optional[str],
        week: Optional[int],
        focus: Optional[str],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Get sessions from JSON files."""
        sessions = []
        if not self.json_dir.exists():
            return sessions

        for json_file in sorted(self.json_dir.glob("*.json"), reverse=True):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                if self._matches_filters(data, phase, week, focus):
                    sessions.append(data)
                    if len(sessions) >= limit:
                        return sessions
            except json.JSONDecodeError:
                continue

        return sessions

    def _get_session_from_json(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get specific session from JSON files."""
        if not self.json_dir.exists():
            return None

        for json_file in self.json_dir.glob("*.json"):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                if data.get("_id") == session_id or data.get("id") == session_id:
                    return data
            except json.JSONDecodeError:
                continue

        return None

    def _search_exercises_in_json(
        self,
        pattern: str,
        limit: int
    ) -> set:
        """Search exercises in JSON files."""
        exercises = set()
        if not self.json_dir.exists():
            return exercises

        for json_file in self.json_dir.glob("*.json"):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                for exercise in data.get("exercises", []):
                    name = exercise.get("Name", "")
                    if pattern.lower() in name.lower():
                        exercises.add(name)
                        if len(exercises) >= limit:
                            return exercises
            except json.JSONDecodeError:
                continue

        return exercises
