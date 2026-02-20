"""Unified LLM interpreter for NL <-> structured app intent/response."""

from typing import Any, Dict, Iterable, Optional

from ai.conversational_ai_service import ConversationalAIService


class LLMInterpreterService:
    """
    Single integration boundary for model interpretation.

    Responsibilities:
    - Natural language -> strict structured intent payloads.
    - Internal system messages -> conversational natural language.
    """

    def __init__(self, ai_service: ConversationalAIService):
        self.ai = ai_service

    def is_enabled(self) -> bool:
        return self.ai.is_enabled()

    def status_message(self) -> str:
        return self.ai.status_message()

    def interpret_workout_input(self, raw: str, *, draft_active: bool) -> Optional[Dict[str, Any]]:
        return self.ai.parse_workout_action(raw, draft_active=draft_active)

    def interpret_metadata_input(
        self,
        raw: str,
        current_metadata: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        return self.ai.parse_metadata_update(raw, current_metadata)

    def to_user_message(self, message: str, *, kind: str = "info") -> str:
        return self.ai.rewrite_message(message, kind=kind)

    def to_user_question(self, question: str) -> str:
        return self.ai.rewrite_question(question)

    def summarize_for_user(self, lines: Iterable[str], *, context: str) -> Optional[str]:
        return self.ai.summarize_lines(lines, context=context)

