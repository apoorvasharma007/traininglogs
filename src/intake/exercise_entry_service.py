"""Service for in-progress exercise draft lifecycle."""

from typing import Any, Dict, Optional, Tuple

from contracts.exercise_contracts import ExerciseDraftContract
from intake.validate_data_service import ValidateDataService


class ExerciseEntryService:
    """Create, mutate, and commit exercise drafts."""

    def __init__(self, validation_service: ValidateDataService):
        self.validation = validation_service

    def create_draft(self, exercise_name: str) -> Dict[str, Any]:
        self.validation.validate_exercise_name(exercise_name)
        return ExerciseDraftContract(name=exercise_name).to_dict()

    @staticmethod
    def has_sets(draft: Optional[Dict[str, Any]]) -> bool:
        if not draft:
            return False
        return bool(draft.get("warmup_sets") or draft.get("working_sets"))

    @staticmethod
    def add_set(draft: Dict[str, Any], set_data: Dict[str, Any], is_warmup: bool) -> None:
        set_key = "warmup_sets" if is_warmup else "working_sets"
        draft.setdefault(set_key, [])
        draft[set_key].append(set_data)

    @staticmethod
    def update_note(draft: Dict[str, Any], note: str) -> None:
        draft["notes"] = note

    @staticmethod
    def undo_last_set(draft: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], str]:
        if draft.get("working_sets"):
            return draft["working_sets"].pop(), "working"
        if draft.get("warmup_sets"):
            return draft["warmup_sets"].pop(), "warmup"
        return None, ""

    def commit_draft(self, agent, session, draft: Dict[str, Any]):
        """Validate and commit draft exercise into session through agent."""
        self.validation.validate_draft_for_commit(draft)
        return agent.log_exercise(
            session,
            draft["name"],
            draft.get("warmup_sets", []),
            draft.get("working_sets", []),
            draft.get("notes"),
        )
