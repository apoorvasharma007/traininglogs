"""
Abstract data source interface.

Services query through this interface - they don't care if data comes
from database, JSON files, or hybrid sources. This enables:
- Easy switching between data sources
- Testing with mock data
- Phase 6.3 (data import) just adds to same source
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime


class DataSource(ABC):
    """Abstract interface for training data access."""

    @abstractmethod
    def get_last_exercise(self, exercise_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent occurrence of an exercise.
        
        Args:
            exercise_name: Name of exercise to query
            
        Returns:
            Exercise data dict or None if not found
        """
        pass

    @abstractmethod
    def get_exercise_history(
        self, 
        exercise_name: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent occurrences of an exercise.
        
        Args:
            exercise_name: Name of exercise
            limit: Maximum number of records to return
            
        Returns:
            List of exercise records, most recent first
        """
        pass

    @abstractmethod
    def get_sessions(
        self, 
        phase: Optional[str] = None,
        week: Optional[int] = None,
        focus: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Query sessions with optional filters.
        
        Args:
            phase: Filter by phase (e.g., "phase 2")
            week: Filter by week number
            focus: Filter by workout focus (e.g., "upper-strength")
            limit: Maximum results
            
        Returns:
            List of session records
        """
        pass

    @abstractmethod
    def save_session(self, session_data: Dict[str, Any]) -> bool:
        """
        Save a completed session.
        
        Args:
            session_data: Complete session dictionary
            
        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific session.
        
        Args:
            session_id: Session UUID
            
        Returns:
            Session data or None
        """
        pass

    @abstractmethod
    def search_exercises(
        self, 
        pattern: str, 
        limit: int = 5
    ) -> List[str]:
        """
        Search for exercises by name pattern.
        
        Args:
            pattern: Exercise name pattern
            limit: Max results
            
        Returns:
            List of matching exercise names
        """
        pass
