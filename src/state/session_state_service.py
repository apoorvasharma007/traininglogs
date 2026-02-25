"""Service for active session and draft state management."""

from typing import Any, Dict, List, Optional, Tuple

from contracts.metadata_contracts import SessionMetadataContract
from services.session_service import Session, SessionMetadata


class SessionStateService:
    """Owns current in-memory session and draft exercise state."""

    STAGE_IDLE = "idle"
    STAGE_AWAITING_EXERCISE = "awaiting_exercise"
    STAGE_EXERCISE_SELECTED = "exercise_selected"
    STAGE_WARMUP_LOGGING = "warmup_logging"
    STAGE_WORKING_LOGGING = "working_logging"

    def __init__(self):
        self._session: Optional[Session] = None
        self._draft: Optional[Dict[str, Any]] = None
        self._dialogue_stage: str = self.STAGE_IDLE

    def start_session(self, agent, metadata: SessionMetadataContract) -> Session:
        self._session = agent.prepare_workout_session(
            phase=metadata.phase,
            week=metadata.week,
            focus=metadata.focus,
            is_deload=metadata.is_deload,
        )
        self._draft = None
        self._dialogue_stage = self.STAGE_AWAITING_EXERCISE
        return self._session

    def restore_from_snapshot(self, snapshot: Dict[str, Any]) -> Tuple[Session, Optional[Dict[str, Any]]]:
        """Rebuild session + draft from live snapshot payload."""
        session_dict = snapshot.get("session", {})
        metadata = SessionMetadata(
            phase=session_dict.get("phase"),
            week=session_dict.get("week"),
            focus=session_dict.get("focus"),
            is_deload=session_dict.get("is_deload", False),
            date=session_dict.get("date"),
        )
        session = Session(
            id=session_dict.get("id"),
            metadata=metadata,
            exercises=session_dict.get("exercises", []),
            created_at=session_dict.get("created_at"),
        )
        self._session = session
        self._draft = snapshot.get("current_exercise")
        self.sync_dialogue_stage_with_draft()
        return session, self._draft

    def get_session(self) -> Session:
        if self._session is None:
            raise ValueError("No active session")
        return self._session

    def get_draft(self) -> Optional[Dict[str, Any]]:
        return self._draft

    def set_draft(self, draft: Optional[Dict[str, Any]]) -> None:
        self._draft = draft
        self.sync_dialogue_stage_with_draft()

    def clear_draft(self) -> None:
        self._draft = None
        self._dialogue_stage = self.STAGE_AWAITING_EXERCISE if self._session else self.STAGE_IDLE

    def reset(self) -> None:
        """Clear in-memory session and draft to bootstrap a new session."""
        self._session = None
        self._draft = None
        self._dialogue_stage = self.STAGE_IDLE

    def get_dialogue_stage(self) -> str:
        return self._dialogue_stage

    def set_dialogue_stage(self, stage: str) -> None:
        self._dialogue_stage = stage

    def sync_dialogue_stage_with_draft(self) -> str:
        """Infer active dialogue stage from current draft contents."""
        if not self._draft:
            if self._session:
                self._dialogue_stage = self.STAGE_AWAITING_EXERCISE
            else:
                self._dialogue_stage = self.STAGE_IDLE
            return self._dialogue_stage

        warmup_count = len(self._draft.get("warmup_sets", []))
        working_count = len(self._draft.get("working_sets", []))
        if working_count > 0:
            self._dialogue_stage = self.STAGE_WORKING_LOGGING
        elif warmup_count > 0:
            self._dialogue_stage = self.STAGE_WARMUP_LOGGING
        else:
            self._dialogue_stage = self.STAGE_EXERCISE_SELECTED
        return self._dialogue_stage

    def committed_exercise_names(self) -> List[str]:
        session = self.get_session()
        return [exercise.get("name", "") for exercise in session.exercises]
