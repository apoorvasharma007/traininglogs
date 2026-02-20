"""Service for turning user input into structured actions."""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from cli.mobile_commands import normalize_command, parse_command, parse_set_notation


@dataclass(frozen=True)
class ParsedAction:
    """Parsed and normalized command/intention."""

    action: str
    argument: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    source: str = "command"  # command | heuristic | memory | llm
    preview: Optional[str] = None
    confidence: float = 1.0


class InputParsingService:
    """Centralized parser: strict commands + LLM interpretation for free-form text."""

    KNOWN_WORKOUT_COMMANDS = {
        "help",
        "status",
        "ex",
        "w",
        "s",
        "note",
        "undo",
        "done",
        "finish",
        "cancel",
        "restart",
    }

    def __init__(self, learning_store_path: str, conversational_ai_service=None):
        # Keep parameter for backward-compatible wiring; local phrase memory removed.
        self.learning_store_path = learning_store_path
        self.ai = conversational_ai_service

    def parse_workout_input(self, raw: str, draft_active: bool) -> Optional[ParsedAction]:
        """Parse one workout-loop input line."""
        phrase_control = self._parse_global_control_phrase(raw)
        if phrase_control:
            return phrase_control

        command, argument = parse_command(raw)
        command = normalize_command(command)

        if command in self.KNOWN_WORKOUT_COMMANDS:
            return ParsedAction(action=command, argument=argument, source="command")

        if not self.ai or not self.ai.is_enabled():
            return None

        llm_interpreted = self.ai.interpret_workout_input(raw, draft_active=draft_active)
        if not llm_interpreted:
            return None

        return ParsedAction(
            action=llm_interpreted["action"],
            payload=llm_interpreted.get("payload", {}),
            source=llm_interpreted.get("source", "llm"),
            preview=llm_interpreted.get("preview"),
            confidence=llm_interpreted.get("confidence", 0.75),
        )

    def parse_metadata_update(
        self,
        raw: str,
        current_metadata: Dict[str, Any],
    ) -> Optional[ParsedAction]:
        """Parse metadata update input."""
        if not self.ai or not self.ai.is_enabled():
            return None

        llm_interpreted = self.ai.interpret_metadata_input(raw, current_metadata)
        if not llm_interpreted:
            return None
        return ParsedAction(
            action=llm_interpreted["action"],
            payload=llm_interpreted.get("payload", {}),
            source=llm_interpreted.get("source", "llm"),
            preview=llm_interpreted.get("preview"),
            confidence=llm_interpreted.get("confidence", 0.75),
        )

    @staticmethod
    def parse_set_argument(raw: str) -> Optional[Dict[str, float]]:
        """Parse compact set notation from command argument."""
        return parse_set_notation(raw)

    def remember_interpretation(self, raw: str, parsed: ParsedAction) -> None:
        """No-op: interpretation memory removed in LLM-only architecture."""
        return

    def _parse_global_control_phrase(self, raw: str) -> Optional[ParsedAction]:
        """
        Parse explicit conversational control phrases before deeper NLP.

        This keeps safety-critical controls deterministic and obvious.
        """
        text = (raw or "").strip()
        lowered = text.lower()
        if not lowered:
            return None

        if lowered in {
            "cancel",
            "quit",
            "exit",
            "stop",
            "quit app",
            "exit app",
            "stop app",
            "quit program",
            "exit program",
            "cancel session",
            "stop session",
        }:
            return ParsedAction(action="cancel", source="command")

        if lowered in {
            "restart",
            "restart session",
            "start over",
            "start fresh",
            "fresh start",
            "new session",
            "restart workout",
            "restart program",
            "restart app",
        }:
            return ParsedAction(action="restart", source="command")

        next_match = re.match(
            r"^(?:go\s+to\s+)?next(?:\s+exercise)?\s+(.+)$",
            text,
            flags=re.IGNORECASE,
        )
        if next_match:
            exercise_name = next_match.group(1).strip()
            if exercise_name:
                return ParsedAction(
                    action="ex",
                    payload={"exercise_name": exercise_name},
                    source="heuristic",
                    preview=f"Start exercise: {exercise_name}",
                    confidence=0.95,
                )

        return None
