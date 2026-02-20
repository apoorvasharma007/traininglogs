"""Wrapper repository for local database operations."""

from typing import Any, Dict, List, Optional


class DatabaseRepository:
    """Wrap existing TrainingSessionRepository with clear data-layer naming."""

    def __init__(self, repo):
        self.repo = repo

    def save_session(self, session_id: str, session_data: Dict[str, Any]) -> bool:
        return self.repo.save_session(session_id, session_data)

    def get_all_sessions(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return self.repo.get_all_sessions(limit=limit)

