"""Render concise conversational text from system state and outcomes."""

from typing import Any, Dict, List, Optional

from contracts.session_contracts import PersistenceOutcomeContract


class ConversationResponseService:
    """Maps internal structures to concise user-facing phrases."""

    def __init__(self, conversational_ai_service=None):
        self.ai = conversational_ai_service

    def _humanize(self, text: str, kind: str) -> str:
        if self.ai and self.ai.is_enabled():
            return self.ai.rewrite_message(text, kind=kind)
        return text

    def metadata_status(self, metadata: Dict[str, Any]) -> str:
        text = (
            "Session metadata"
            f" | phase={metadata.get('phase')}"
            f" | week={metadata.get('week')}"
            f" | focus={metadata.get('focus')}"
            f" | deload={metadata.get('is_deload')}"
        )
        return self._humanize(text, "status")

    def mobile_status_lines(self, session, draft: Optional[Dict[str, Any]]) -> List[str]:
        lines = [f"Session {session.id[:8]} | Exercises committed: {len(session.exercises)}"]
        if not draft:
            lines.append("No active draft exercise. Start one with: ex <name>")
            return [self._humanize(line, "status") for line in lines]

        lines.append(
            f"Draft: {draft['name']} | warmups={len(draft.get('warmup_sets', []))} "
            f"working={len(draft.get('working_sets', []))}"
        )
        if draft.get("notes"):
            lines.append(f"Note: {draft['notes']}")
        return [self._humanize(line, "status") for line in lines]

    def persistence_lines(self, outcome: PersistenceOutcomeContract, db_path: str) -> List[str]:
        lines: List[str] = []

        if outcome.status == "not_saved":
            return [self._humanize("Session not saved.", "persistence")]

        if not outcome.saved_local:
            lines.append(
                self._humanize(
                    f"Local DB save failed: {outcome.local_error or 'unknown error'}",
                    "error",
                )
            )
            return lines

        lines.append(self._humanize("Session saved locally.", "success"))
        lines.append(self._humanize(f"Database: {db_path}", "persistence"))

        if outcome.saved_json:
            lines.append(self._humanize("JSON export saved in data/output/sessions/", "persistence"))
        elif outcome.json_error:
            lines.append(self._humanize(f"JSON export warning: {outcome.json_error}", "warning"))

        if outcome.cloud_mode == "disabled":
            lines.append(
                self._humanize(
                    "Cloud save disabled (set TRAININGLOGS_CLOUD_POSTGRES_DSN to enable).",
                    "persistence",
                )
            )
        elif outcome.saved_cloud:
            lines.append(self._humanize("Cloud database save succeeded.", "success"))
        else:
            lines.append(
                self._humanize(
                    f"Cloud save warning: {outcome.cloud_error or 'not written'}",
                    "warning",
                )
            )

        return lines
