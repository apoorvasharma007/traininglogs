"""Abstract data source interface used by domain services."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class DataSource(ABC):
    """Minimal contract for history/session queries."""

    @abstractmethod
    def get_last_exercise(self, exercise_name: str) -> Optional[Dict[str, Any]]:
        """Return most recent matching exercise payload."""

    @abstractmethod
    def get_exercise_history(self, exercise_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Return recent matching exercise payloads, newest-first."""

    @abstractmethod
    def get_sessions(
        self,
        phase: Optional[str] = None,
        week: Optional[int] = None,
        focus: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return session payloads with optional filters."""

    @abstractmethod
    def save_session(self, session_data: Dict[str, Any]) -> bool:
        """Persist one completed session payload."""

    @abstractmethod
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return one session payload by id."""

    @abstractmethod
    def search_exercises(self, pattern: str, limit: int = 5) -> List[str]:
        """Return matching exercise names."""
