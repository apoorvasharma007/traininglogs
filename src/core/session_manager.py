"""
Session management for traininglogs.

Maintains in-memory session state and coordinates persistence.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from uuid import uuid4
from core.validators import Validators, ValidationError
from persistence import TrainingSessionRepository
from persistence.exporter import SessionExporter


class SessionManager:
    """Manages training session lifecycle."""

    def __init__(self, repository: TrainingSessionRepository):
        """
        Initialize SessionManager.
        
        Args:
            repository: TrainingSessionRepository instance
        """
        self.repository = repository
        self.validators = Validators()
        self.exporter = SessionExporter()
        self.current_session: Optional[Dict[str, Any]] = None

    def start_session(
        self,
        date: Optional[str] = None,
        phase: Optional[str] = None,
        week: Optional[int] = None,
        focus: Optional[str] = None,
        is_deload: bool = False
    ) -> Dict[str, Any]:
        """
        Start a new training session.
        
        Args:
            date: Session date (ISO format, defaults to today)
            phase: Training phase (e.g., "phase 2")
            week: Week number
            focus: Workout focus (e.g., "upper-strength")
            is_deload: Whether this is a deload week
            
        Returns:
            Session dictionary
        """
        session_id = str(uuid4())
        session_date = date or datetime.now().isoformat()

        self.current_session = {
            "id": session_id,
            "date": session_date,
            "phase": phase,
            "week": week,
            "focus": focus,
            "is_deload": is_deload,
            "exercises": [],
            "created_at": datetime.now().isoformat()
        }

        return self.current_session

    def add_exercise(
        self,
        name: str,
        warmup_sets: Optional[List[Dict[str, Any]]] = None,
        working_sets: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Add exercise to current session.
        
        Args:
            name: Exercise name
            warmup_sets: Optional list of warmup sets
            working_sets: Optional list of working sets
            
        Returns:
            Exercise dictionary
            
        Raises:
            RuntimeError: If no session is in progress
        """
        if self.current_session is None:
            raise RuntimeError("No session in progress. Call start_session() first.")

        exercise = {
            "name": name,
            "warmup_sets": warmup_sets or [],
            "working_sets": working_sets or []
        }

        self.current_session["exercises"].append(exercise)
        return exercise

    def finish_session(self) -> Dict[str, Any]:
        """
        Finish current session and prepare for persistence.
        
        Returns:
            Completed session dictionary
            
        Raises:
            RuntimeError: If no session is in progress
            ValidationError: If session fails validation
        """
        if self.current_session is None:
            raise RuntimeError("No session in progress.")

        # Validate session before finishing
        try:
            self.validators.validate_session(self.current_session)
        except ValidationError as e:
            raise ValidationError(f"Cannot finish session: {e}")

        return self.current_session

    def cancel_session(self):
        """Cancel current session without saving."""
        self.current_session = None

    def get_current_session(self) -> Optional[Dict[str, Any]]:
        """
        Get current session.
        
        Returns:
            Current session dictionary or None
        """
        return self.current_session

    def persist_session(self) -> bool:
        """
        Persist current session to database AND export to JSON file.
        
        Returns:
            True if successful
            
        Raises:
            RuntimeError: If no session in progress
            Exception: On database write error
        """
        if self.current_session is None:
            raise RuntimeError("No session to persist.")

        session_id = self.current_session["id"]

        try:
            # Save to database
            self.repository.save_session(session_id, self.current_session)
            
            # Export to JSON file for permanent, readable record
            export_path = self.exporter.export_session(self.current_session)
            self.current_session = None  # Clear session after saving
            
            return True
        except Exception as e:
            raise Exception(f"Failed to persist session: {e}")

    def load_session(self, session_id: str) -> Dict[str, Any]:
        """
        Load a previously saved session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session dictionary
            
        Raises:
            Exception: If session not found
        """
        session = self.repository.get_session(session_id)
        if session is None:
            raise Exception(f"Session not found: {session_id}")
        return session
