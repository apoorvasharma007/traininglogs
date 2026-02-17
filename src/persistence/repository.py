"""
Repository layer for training session persistence.

All database access goes through this layer.
"""

import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from persistence.database import Database


class TrainingSessionRepository:
    """Repository for training session persistence."""

    def __init__(self, db: Database):
        """
        Initialize repository.
        
        Args:
            db: Database instance
        """
        self.db = db

    def save_session(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        """
        Save training session to database.
        
        Args:
            session_id: Unique session identifier
            session_data: Dictionary containing session data
            
        Returns:
            True if successful
            
        Raises:
            Exception: On database write error
        """
        try:
            # Extract metadata
            date = session_data.get("date", datetime.now().isoformat())
            phase = session_data.get("phase")
            week = session_data.get("week")
            raw_json = json.dumps(session_data)
            created_at = datetime.now().isoformat()

            self.db.execute(
                """
                INSERT OR REPLACE INTO training_sessions 
                (id, date, phase, week, raw_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, date, phase, week, raw_json, created_at)
            )
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to save session: {e}")

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a training session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session dictionary or None if not found
        """
        try:
            cursor = self.db.execute(
                "SELECT raw_json FROM training_sessions WHERE id = ?",
                (session_id,)
            )
            result = cursor.fetchone()
            if result:
                return json.loads(result[0])
            return None
        except Exception as e:
            raise Exception(f"Failed to get session: {e}")

    def get_sessions_by_date(self, date: str) -> List[Dict[str, Any]]:
        """
        Retrieve all sessions for a specific date.
        
        Args:
            date: Date string (YYYY-MM-DD)
            
        Returns:
            List of session dictionaries
        """
        try:
            cursor = self.db.execute(
                """
                SELECT raw_json FROM training_sessions 
                WHERE date = ? 
                ORDER BY created_at DESC
                """,
                (date,)
            )
            results = cursor.fetchall()
            return [json.loads(row[0]) for row in results]
        except Exception as e:
            raise Exception(f"Failed to get sessions by date: {e}")

    def get_sessions_by_phase(self, phase: str) -> List[Dict[str, Any]]:
        """
        Retrieve all sessions for a specific phase.
        
        Args:
            phase: Phase name
            
        Returns:
            List of session dictionaries
        """
        try:
            cursor = self.db.execute(
                """
                SELECT raw_json FROM training_sessions 
                WHERE phase = ? 
                ORDER BY created_at DESC
                """,
                (phase,)
            )
            results = cursor.fetchall()
            return [json.loads(row[0]) for row in results]
        except Exception as e:
            raise Exception(f"Failed to get sessions by phase: {e}")

    def get_sessions_by_phase_and_week(self, phase: str, week: int) -> List[Dict[str, Any]]:
        """
        Retrieve sessions for a specific phase and week.
        
        Args:
            phase: Phase name
            week: Week number
            
        Returns:
            List of session dictionaries
        """
        try:
            cursor = self.db.execute(
                """
                SELECT raw_json FROM training_sessions 
                WHERE phase = ? AND week = ?
                ORDER BY created_at DESC
                """,
                (phase, week)
            )
            results = cursor.fetchall()
            return [json.loads(row[0]) for row in results]
        except Exception as e:
            raise Exception(f"Failed to get sessions by phase and week: {e}")

    def get_all_sessions(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve all training sessions, ordered by date descending.
        
        Args:
            limit: Optional limit on number of results
            
        Returns:
            List of session dictionaries
        """
        try:
            limit_clause = f"LIMIT {limit}" if limit else ""
            cursor = self.db.execute(
                f"""
                SELECT raw_json FROM training_sessions 
                ORDER BY date DESC, created_at DESC
                {limit_clause}
                """
            )
            results = cursor.fetchall()
            return [json.loads(row[0]) for row in results]
        except Exception as e:
            raise Exception(f"Failed to get all sessions: {e}")

    def get_last_occurrence_of_exercise(self, exercise_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent session containing a specific exercise.
        
        Args:
            exercise_name: Name of exercise to search for
            
        Returns:
            Exercise details from most recent session or None
        """
        try:
            # Note: This is a basic implementation.
            # For better performance, consider adding a separate exercises table.
            cursor = self.db.execute(
                """
                SELECT raw_json FROM training_sessions 
                ORDER BY date DESC, created_at DESC
                LIMIT 50
                """
            )
            results = cursor.fetchall()
            
            for row in results:
                session = json.loads(row[0])
                exercises = session.get("exercises", [])
                for exercise in exercises:
                    if exercise.get("name", "").lower() == exercise_name.lower():
                        return exercise
            
            return None
        except Exception as e:
            raise Exception(f"Failed to get exercise history: {e}")

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a training session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful
        """
        try:
            self.db.execute(
                "DELETE FROM training_sessions WHERE id = ?",
                (session_id,)
            )
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Failed to delete session: {e}")

    def count_sessions(self) -> int:
        """
        Count total number of sessions.
        
        Returns:
            Number of sessions
        """
        try:
            cursor = self.db.execute("SELECT COUNT(*) FROM training_sessions")
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            raise Exception(f"Failed to count sessions: {e}")
