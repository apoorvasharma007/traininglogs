"""User conversation loop helpers (prompt, retry, confirm, display)."""

from typing import Any, Dict, Iterable, Optional

from cli import prompts
from conversation.conversation_response_service import ConversationResponseService
from core.validators import ValidationError


class UserConversationService:
    """All user-facing conversation behavior for the CLI workflow."""

    def __init__(self, response_service: ConversationResponseService, conversational_ai_service=None):
        self.responses = response_service
        self.ai = conversational_ai_service

    def _to_user_text(self, message: str, kind: str, use_ai: bool = True) -> str:
        if use_ai and self.ai and self.ai.is_enabled():
            return self.ai.to_user_message(message, kind=kind)
        return message

    def show_info(self, message: str, use_ai: bool = True) -> None:
        prompts.show_info(self._to_user_text(message, "info", use_ai=use_ai))

    def show_error(self, message: str, use_ai: bool = True) -> None:
        prompts.show_error(self._to_user_text(message, "error", use_ai=use_ai))

    def show_success(self, message: str, use_ai: bool = True) -> None:
        prompts.show_success(self._to_user_text(message, "success", use_ai=use_ai))

    @staticmethod
    def prompt_command() -> str:
        return prompts.prompt_mobile_command()

    def confirm_action(self, text: str) -> bool:
        question = text
        if self.ai and self.ai.is_enabled():
            question = self.ai.to_user_question(text)
        return prompts.confirm_action(question)

    @staticmethod
    def confirm_save() -> bool:
        return prompts.confirm_save()

    def show_help(self) -> None:
        if self.ai and self.ai.is_enabled():
            prompts.show_info(self.ai.to_user_message("Command cheat sheet:", kind="help"))
        prompts.show_mobile_help()

    @staticmethod
    def show_summary(session_dict: Dict[str, Any]) -> None:
        prompts.show_session_summary(session_dict)

    def show_metadata_status(self, metadata: Dict[str, Any]) -> None:
        self.show_info(self.responses.metadata_status(metadata))

    def show_mobile_status(self, session, draft: Dict[str, Any]) -> None:
        for line in self.responses.mobile_status_lines(session, draft):
            self.show_info(line, use_ai=False)

    def show_history_lines(self, lines: Iterable[str]) -> None:
        history_lines = list(lines)
        if self.ai and self.ai.is_enabled():
            summary = self.ai.summarize_for_user(history_lines, context="exercise history guidance")
            if summary:
                self.show_info(summary, use_ai=False)
                return
        for line in history_lines:
            self.show_info(line)

    def show_persistence_outcome(self, outcome, db_path: str) -> None:
        lines = self.responses.persistence_lines(outcome, db_path)
        if not lines:
            return

        if outcome.status == "not_saved":
            for line in lines:
                self.show_info(line, use_ai=False)
            return

        if outcome.saved_local:
            self.show_success(lines[0], use_ai=False)
            for line in lines[1:]:
                self.show_info(line, use_ai=False)
            return

        self.show_error(lines[0], use_ai=False)
        for line in lines[1:]:
            self.show_info(line, use_ai=False)

    def collect_metadata(self, metadata_service) -> Optional[Dict[str, Any]]:
        """Conversational metadata intake loop with retry-until-valid behavior."""
        metadata = metadata_service.default_metadata()

        self.show_info("Let's set session metadata conversationally.")
        self.show_info(
            "Describe metadata in one sentence or iteratively."
            " Example: 'phase 2 week 7 pull-hypertrophy no deload'."
        )
        self.show_info(
            "Controls: 'status' to inspect, 'done' to continue, "
            "'reset' to start over, 'cancel' to exit."
            " You can also type 'quit' or 'exit'."
        )
        self.show_metadata_status(metadata)

        while True:
            raw = self.prompt_command()
            lowered = (raw or "").strip().lower()

            if lowered in {"help", "/help", "?"}:
                self.show_info(
                    "Metadata commands: status | done | reset | cancel"
                )
                self.show_info(
                    "Example: phase 2 week 7 upper-strength no deload"
                )
                continue

            if lowered in {"status", "show"}:
                self.show_metadata_status(metadata)
                continue

            if lowered in {"reset", "restart", "start over", "startover"} or (
                "fresh start" in lowered
            ):
                metadata = metadata_service.default_metadata()
                self.show_info("Metadata reset to defaults.")
                self.show_metadata_status(metadata)
                continue

            wants_cancel = lowered in {"cancel", "quit", "exit", "stop"} or any(
                phrase in lowered
                for phrase in {
                    "cancel setup",
                    "quit setup",
                    "exit setup",
                    "stop setup",
                    "stop session",
                    "exit program",
                    "quit program",
                }
            )
            if wants_cancel:
                if self.confirm_action("Cancel setup and exit now?"):
                    return None
                continue

            if lowered in {"done", "start"}:
                self.show_metadata_status(metadata)
                if self.confirm_action("Use this metadata and start session?"):
                    return metadata
                continue

            try:
                preview, candidate = metadata_service.preview_and_apply_update(raw, metadata)
            except ValidationError as err:
                self.show_error(str(err))
                continue

            self.show_info(f"I understood: {preview}")
            self.show_metadata_status(candidate)
            if not self.confirm_action("Apply this metadata update?"):
                self.show_info("No problem. Rephrase the metadata update.")
                continue

            metadata = candidate
            self.show_metadata_status(metadata)
            if self.confirm_action("Start session with this metadata now?"):
                return metadata
