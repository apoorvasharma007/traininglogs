"""Agent brain for turn-level orchestration over parser + tool router."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentTurnResult:
    """Result after processing one user turn."""

    outcome: str  # continue | finish | restart | exit
    exit_code: int = 0


class AgentControllerService:
    """
    Conversational controller for one user turn.

    Responsibilities:
    - Interpret raw user text through the LLM parsing layer.
    - Show/confirm interpreted intent when needed.
    - Route confirmed intents to deterministic tool handlers.
    - Produce stage-agnostic outcomes for workflow orchestration.
    """

    def __init__(self, conversation, parsing, state, intent_router):
        self.conversation = conversation
        self.parsing = parsing
        self.state = state
        self.intent_router = intent_router

    def handle_user_turn(self, raw: str, *, restart_exit_code: int) -> AgentTurnResult:
        """Process one user input turn and return control outcome."""
        draft = self.state.get_draft()
        parsed = self.parsing.parse_workout_input(raw, draft_active=bool(draft))
        if not parsed:
            self._handle_parse_failure(raw, draft_active=bool(draft))
            return AgentTurnResult("continue")

        if parsed.requires_confirmation:
            preview = parsed.preview or f"Apply action: {parsed.action}"
            self.conversation.show_info(f"I understood: {preview}")
            if not self.conversation.confirm_action("Use this interpretation?"):
                self.conversation.show_info("No problem. Rephrase the message.")
                return AgentTurnResult("continue")
            self.parsing.remember_interpretation(raw, parsed)

        route_result = self.intent_router.route(parsed, restart_exit_code=restart_exit_code)
        if route_result.outcome == "continue" and route_result.prompt_next:
            self._show_next_prompt(parsed.action)
        return AgentTurnResult(outcome=route_result.outcome, exit_code=route_result.exit_code)

    def _handle_parse_failure(self, raw: str, *, draft_active: bool) -> None:
        """Provide recovery prompts when parser cannot map input to intent."""
        lowered = (raw or "").strip().lower()
        if lowered in {"y", "yes", "yeah", "yep", "n", "no", "nope"}:
            self._show_no_pending_confirmation_hint()
            return

        if draft_active and "warmup" in lowered and "set" in lowered:
            self.conversation.show_info(
                "Got it. Add the first warmup set like `w 20x8` (or `w 0x10` for bodyweight)."
            )
            return
        if draft_active and "working" in lowered and "set" in lowered:
            self.conversation.show_info("Great. Add the first working set like `s 80x6@8`.")
            return
        if draft_active and lowered in {"set", "sets", "first set"}:
            self.conversation.show_info(
                "Tell me the set directly, for example `w 20x8` or `s 80x6@8`."
            )
            return

        if self.parsing.is_ai_enabled():
            self.conversation.show_error("I couldn't parse that yet. Rephrase it, or type `help` for examples.")
        else:
            self.conversation.show_error(
                "I couldn't parse that input. Type `help` for strict commands, "
                "or enable LLM mode with TRAININGLOGS_LLM_ENABLED=true for natural language."
            )

    def _show_no_pending_confirmation_hint(self) -> None:
        """Guide yes/no replies when no confirmation question is active."""
        draft = self.state.get_draft()
        if not draft:
            self.conversation.show_info(
                "No confirmation is pending. Tell me the next exercise name, or type `finish` to end the session."
            )
            return

        warmups = len(draft.get("warmup_sets", []))
        working = len(draft.get("working_sets", []))
        if warmups == 0 and working == 0:
            self.conversation.show_info(
                "No confirmation is pending. Add your first set like `w 0x10` or `s 20x8`."
            )
            return
        if working == 0:
            self.conversation.show_info(
                "No confirmation is pending. Add another warmup, or start working sets with `s <weight>x<reps>`."
            )
            return
        self.conversation.show_info(
            "No confirmation is pending. Add your next working set, or type `done` to commit this exercise."
        )

    def _show_next_prompt(self, action: str) -> None:
        """
        Ask one concise stage-aware follow-up question after a successful turn.

        This keeps conversation momentum without dumping command help repeatedly.
        """
        if action in {"help", "status"}:
            return

        draft = self.state.get_draft()
        stage = self.state.get_dialogue_stage()

        if action == "done":
            self.conversation.show_info(
                "Exercise saved. Want to log another exercise, or type `finish` to end the session."
            )
            return

        if not draft:
            if stage == "awaiting_exercise":
                self.conversation.show_info(
                    "Tell me the next exercise when you're ready."
                )
            return

        warmups = len(draft.get("warmup_sets", []))
        working = len(draft.get("working_sets", []))

        if action == "ex":
            self.conversation.show_info(
                "Great. Give me your first set for this exercise (for example `w 0x10` or `s 20x8`)."
            )
            return

        if action in {"w", "w_batch"}:
            if working == 0:
                self.conversation.show_info(
                    "Nice. Add another warmup, or start your first working set."
                )
            else:
                self.conversation.show_info(
                    "Nice. Add the next working set, or type `done` when this exercise is complete."
                )
            return

        if action == "s":
            self.conversation.show_info(
                "Logged. Add the next working set, or type `done` to commit this exercise."
            )
            return

        if action in {"note", "goal", "rest", "tempo", "muscles", "cue", "warmup_note", "undo"}:
            if warmups == 0 and working == 0:
                self.conversation.show_info(
                    "Now add your first set (`w` for warmup or `s` for working)."
                )
            elif working == 0:
                self.conversation.show_info(
                    "You can keep adding warmups, switch to working sets, or type `done` when ready."
                )
            else:
                self.conversation.show_info(
                    "You can add more sets, update notes/goal, or type `done` to save this exercise."
                )
