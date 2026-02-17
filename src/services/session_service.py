"""
Session service - manages workout session lifecycle.

Handles session creation, exercise addition, and finalization.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4
from core.validators import Validators, ValidationError


@dataclass
class SessionMetadata:
    """Session metadata."""
    phase: str
    week: int
    focus: str
    is_deload: bool
    date: Optional[str] = None


@dataclass
class Session:
    """Complete session with all exercises."""
    id: str
    metadata: SessionMetadata
    exercises: List[Dict[str, Any]]
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "date": self.metadata.date,
            "phase": self.metadata.phase,
            "week": self.metadata.week,
            "focus": self.metadata.focus,
            "is_deload": self.metadata.is_deload,
            "exercises": self.exercises,
            "created_at": self.created_at
        }


class SessionService:
    """Manage session lifecycle."""

    def __init__(self):
        """Initialize session service."""
        self.validators = Validators()

    def create_session(self, metadata: SessionMetadata) -> Session:
        """
        Create a new session.
        
        Args:
            metadata: Session metadata
            
        Returns:
            New Session object
            
        Raises:
            ValidationError: If metadata invalid
        """
        # Validate metadata
        self._validate_metadata(metadata)

        session = Session(
            id=str(uuid4()),
            metadata=SessionMetadata(
                phase=metadata.phase,
                week=metadata.week,
                focus=metadata.focus,
                is_deload=metadata.is_deload,
                date=metadata.date or datetime.now().isoformat()
            ),
            exercises=[],
            created_at=datetime.now().isoformat()
        )
        return session

    def add_exercise(
        self,
        session: Session,
        exercise: Dict[str, Any]
    ) -> bool:
        """
        Add exercise to session.
        
        Args:
            session: Session to add to
            exercise: Exercise data
            
        Returns:
            True if added successfully
            
        Raises:
            ValidationError: If exercise invalid
        """
        if not exercise or not exercise.get("name"):
            raise ValidationError("Exercise name required")

        session.exercises.append(exercise)
        return True

    def finalize_session(self, session: Session) -> Session:
        """
        Finalize and prepare session for persistence.
        
        Args:
            session: Session to finalize
            
        Returns:
            Finalized session
            
        Raises:
            ValidationError: If session invalid
        """
        if not session.exercises:
            raise ValidationError("Session must have at least one exercise")

        # All validation on individual exercises happened during add
        # Just confirm we have a valid state
        return session

    def get_session_summary(self, session: Session) -> str:
        """
        Get human-readable session summary.
        
        Args:
            session: Session to summarize
            
        Returns:
            Summary string
        """
        meta = session.metadata
        summary = f"Session: {meta.phase} Week {meta.week} ({meta.focus})"

        if meta.is_deload:
            summary += " [DELOAD]"

        summary += f"\nExercises: {len(session.exercises)}"

        for idx, ex in enumerate(session.exercises, 1):
            summary += f"\n  {idx}. {ex.get('name', 'Unknown')}"

        return summary

    # Private helpers

    def _validate_metadata(self, metadata: SessionMetadata) -> bool:
        """Validate session metadata."""
        errors = []

        if not metadata.phase:
            errors.append("Phase required")
        if metadata.week is None or metadata.week < 1:
            errors.append("Week must be >= 1")
        if not metadata.focus:
            errors.append("Focus required")

        if errors:
            raise ValidationError("; ".join(errors))

        return True
