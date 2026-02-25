"""Intent router that maps parsed actions to deterministic workflow operations."""

from dataclasses import dataclass
from typing import Optional

from core.validators import ValidationError


@dataclass(frozen=True)
class RouteResult:
    """Result of routing one parsed user action."""

    outcome: str  # continue | finish | exit | restart
    exit_code: int = 0
    prompt_next: bool = False


class IntentRouterService:
    """Executes parsed intents against current session state and services."""

    def __init__(
        self,
        agent,
        conversation,
        exercise_entry,
        history_guidance,
        parsing,
        validation,
        state,
        persistence,
    ):
        self.agent = agent
        self.conversation = conversation
        self.exercise_entry = exercise_entry
        self.history_guidance = history_guidance
        self.parsing = parsing
        self.validation = validation
        self.state = state
        self.persistence = persistence

    def route(self, parsed, *, restart_exit_code: int) -> RouteResult:
        """Route one parsed action."""
        session = self.state.get_session()
        draft = self.state.get_draft()

        command = parsed.action
        argument = parsed.argument

        if command == "help":
            self.conversation.show_help()
            return RouteResult("continue")

        if command == "status":
            self.conversation.show_mobile_status(session, draft)
            return RouteResult("continue")

        if command == "ex":
            exercise_name = parsed.payload.get("exercise_name") if parsed.payload else argument
            if not exercise_name:
                self.conversation.show_error("Usage: ex <exercise name>")
                return RouteResult("continue")
            try:
                self.validation.validate_exercise_name(exercise_name)
            except ValidationError as err:
                self.conversation.show_error(str(err))
                return RouteResult("continue")

            if self.exercise_entry.has_sets(draft):
                if not self.conversation.confirm_action("Discard current draft and start new exercise?"):
                    return RouteResult("continue")

            context = self.history_guidance.get_logging_context(exercise_name)
            self.conversation.show_history_lines(self.history_guidance.to_concise_lines(context))
            new_draft = self.exercise_entry.create_draft(exercise_name)
            self.state.set_draft(new_draft)

            self.persistence.append_event(
                session.id,
                "exercise_started",
                {"exercise_name": exercise_name},
            )
            self.state.sync_dialogue_stage_with_draft()
            self.persistence.update_snapshot(session.to_dict(), current_exercise=new_draft)
            return RouteResult("continue", prompt_next=True)

        if command in {"w", "s"}:
            if not draft:
                self.conversation.show_error("No active draft. Start one with: ex <exercise name>")
                return RouteResult("continue")

            set_data = parsed.payload.get("set_data") if parsed.payload else self.parsing.parse_set_argument(argument)
            if not set_data:
                self.conversation.show_error("Invalid set format. Use: 80x5 or 80x5@8")
                return RouteResult("continue")

            is_warmup = command == "w"
            try:
                normalized = self.validation.normalize_and_validate_set_data(set_data, is_warmup=is_warmup)
            except ValidationError as err:
                self.conversation.show_error(str(err))
                return RouteResult("continue")

            self.exercise_entry.add_set(draft, normalized, is_warmup=is_warmup)
            set_key = "warmup_sets" if is_warmup else "working_sets"
            self.persistence.append_event(
                session.id,
                "set_added",
                {
                    "exercise_name": draft["name"],
                    "set_type": "warmup" if is_warmup else "working",
                    "set_data": normalized,
                    "set_index": len(draft[set_key]),
                },
            )
            self.state.sync_dialogue_stage_with_draft()
            self.persistence.update_snapshot(session.to_dict(), current_exercise=draft)
            self.conversation.show_success(
                f"Added {'warmup' if is_warmup else 'working'} set: "
                f"{normalized['weight']}kg x {normalized['reps']}"
            )
            return RouteResult("continue", prompt_next=True)

        if command == "w_batch":
            if not draft:
                self.conversation.show_error("No active draft. Start one with: ex <exercise name>")
                return RouteResult("continue")

            payload = parsed.payload or {}
            try:
                count = int(payload.get("count"))
            except (TypeError, ValueError):
                self.conversation.show_error("Warmup batch needs a valid set count.")
                return RouteResult("continue")
            if count < 1 or count > 20:
                self.conversation.show_error("Warmup set count must be between 1 and 20.")
                return RouteResult("continue")

            set_data = payload.get("set_data", {})
            feel_reps = bool(payload.get("feel_reps", False))
            if feel_reps and set_data.get("reps") is None:
                try:
                    weight = float(set_data.get("weight"))
                except (TypeError, ValueError):
                    self.conversation.show_error("Warmup batch needs a valid weight.")
                    return RouteResult("continue")
                for _ in range(count):
                    self.exercise_entry.add_set(
                        draft,
                        {"weight": weight, "reps": None, "rep_mode": "feel"},
                        is_warmup=True,
                    )
                self.persistence.append_event(
                    session.id,
                    "warmup_batch_added",
                    {
                        "exercise_name": draft["name"],
                        "count": count,
                        "weight": weight,
                        "rep_mode": "feel",
                    },
                )
                self.state.sync_dialogue_stage_with_draft()
                self.persistence.update_snapshot(session.to_dict(), current_exercise=draft)
                self.conversation.show_success(
                    f"Added {count} warmup sets at {weight}kg with feel reps."
                )
                return RouteResult("continue", prompt_next=True)

            try:
                normalized = self.validation.normalize_and_validate_set_data(set_data, is_warmup=True)
            except ValidationError as err:
                self.conversation.show_error(str(err))
                return RouteResult("continue")

            for _ in range(count):
                self.exercise_entry.add_set(draft, normalized, is_warmup=True)
            self.persistence.append_event(
                session.id,
                "warmup_batch_added",
                {
                    "exercise_name": draft["name"],
                    "count": count,
                    "set_data": normalized,
                },
            )
            self.state.sync_dialogue_stage_with_draft()
            self.persistence.update_snapshot(session.to_dict(), current_exercise=draft)
            self.conversation.show_success(
                f"Added {count} warmup sets: {normalized['weight']}kg x {normalized['reps']}."
            )
            return RouteResult("continue", prompt_next=True)

        if command in {"note", "goal", "rest", "tempo", "muscles", "cue", "warmup_note"}:
            return self._handle_exercise_metadata_update(command, parsed, argument, session.id, draft)

        if command == "undo":
            if not draft:
                self.conversation.show_error("No active draft to undo.")
                return RouteResult("continue")

            removed, set_type = self.exercise_entry.undo_last_set(draft)
            if removed is None:
                self.conversation.show_error("Draft has no sets to undo.")
                return RouteResult("continue")

            self.persistence.append_event(
                session.id,
                "set_removed",
                {
                    "exercise_name": draft["name"],
                    "set_type": set_type,
                    "set_data": removed,
                },
            )
            self.state.sync_dialogue_stage_with_draft()
            self.persistence.update_snapshot(session.to_dict(), current_exercise=draft)
            self.conversation.show_info("Removed last set from draft.")
            return RouteResult("continue", prompt_next=True)

        if command == "done":
            if not draft:
                self.conversation.show_error("No active draft to commit.")
                return RouteResult("continue")

            try:
                success, error = self.exercise_entry.commit_draft(self.agent, session, draft)
            except ValidationError as err:
                self.conversation.show_error(str(err))
                return RouteResult("continue")

            if success:
                self.persistence.append_event(
                    session.id,
                    "exercise_committed",
                    {
                        "exercise_name": draft["name"],
                        "warmup_count": len(draft.get("warmup_sets", [])),
                        "working_count": len(draft.get("working_sets", [])),
                    },
                )
                self.persistence.update_snapshot(session.to_dict(), current_exercise=None)
                self.conversation.show_success(f"Added: {draft['name']}")

                completed = self.state.committed_exercise_names()
                next_suggestions = self.agent.get_next_exercise_suggestions(
                    session.metadata.focus,
                    completed,
                    limit=3,
                )
                if next_suggestions:
                    self.conversation.show_info(f"Next suggestions: {', '.join(next_suggestions)}")

                self.state.clear_draft()
                return RouteResult("continue", prompt_next=True)
            else:
                self.conversation.show_error(self.agent.get_error_recovery_hints(error))
            return RouteResult("continue")

        if command == "finish":
            if self.exercise_entry.has_sets(draft):
                self.conversation.show_error(
                    "You still have an active draft. Use done or ex <new> to discard."
                )
                return RouteResult("continue")
            return RouteResult("finish")

        if command == "cancel":
            if self.conversation.confirm_action("Cancel session without saving?"):
                self.persistence.close_session(session.to_dict(), status="cancelled")
                self.state.reset()
                self.conversation.show_info("Session cancelled.")
                return RouteResult("exit", exit_code=0)
            return RouteResult("continue")

        if command == "restart":
            if self.conversation.confirm_action("Discard this session and restart from fresh setup?"):
                self.persistence.close_session(session.to_dict(), status="restarted")
                self.state.reset()
                self.conversation.show_info("Restarting from fresh session setup.")
                return RouteResult("restart", exit_code=restart_exit_code)
            return RouteResult("continue")

        self.conversation.show_error("Unknown command. Type help.")
        return RouteResult("continue")

    def _handle_exercise_metadata_update(
        self,
        command: str,
        parsed,
        argument: str,
        session_id: str,
        draft: Optional[dict],
    ) -> RouteResult:
        if not draft:
            self.conversation.show_error("No active draft. Start one with: ex <exercise name>")
            return RouteResult("continue")

        if command == "note":
            text = parsed.payload.get("note") if parsed.payload else argument
            if not text:
                self.conversation.show_error("Usage: note <text>")
                return RouteResult("continue")
            self.exercise_entry.update_note(draft, text)
            event_type = "note_updated"
            payload = {"exercise_name": draft["name"], "note": text}
            success_text = "Exercise note updated."

        elif command == "goal":
            goal_payload = parsed.payload.get("goal") if parsed.payload else self._parse_goal_argument(argument)
            try:
                goal = self.validation.normalize_and_validate_goal_data(goal_payload)
            except (ValidationError, TypeError, ValueError) as err:
                self.conversation.show_error(str(err))
                return RouteResult("continue")
            self.exercise_entry.update_goal(draft, goal)
            event_type = "goal_updated"
            payload = {"exercise_name": draft["name"], "goal": goal}
            success_text = "Exercise goal updated."

        elif command == "rest":
            rest_raw = parsed.payload.get("rest_minutes") if parsed.payload else argument
            try:
                rest_minutes = int(rest_raw)
                if rest_minutes < 0:
                    raise ValueError
            except (TypeError, ValueError):
                self.conversation.show_error("Usage: rest <minutes>, minutes must be >= 0")
                return RouteResult("continue")
            self.exercise_entry.update_rest_minutes(draft, rest_minutes)
            event_type = "rest_updated"
            payload = {"exercise_name": draft["name"], "rest_minutes": rest_minutes}
            success_text = "Exercise rest updated."

        elif command == "tempo":
            tempo = parsed.payload.get("tempo") if parsed.payload else argument
            tempo = str(tempo or "").strip()
            if not tempo:
                self.conversation.show_error("Usage: tempo <pattern>")
                return RouteResult("continue")
            self.exercise_entry.update_tempo(draft, tempo)
            event_type = "tempo_updated"
            payload = {"exercise_name": draft["name"], "tempo": tempo}
            success_text = "Exercise tempo updated."

        elif command == "muscles":
            muscles = parsed.payload.get("muscles") if parsed.payload else argument
            self.exercise_entry.update_muscles(draft, muscles)
            normalized = draft.get("muscles") or []
            if not normalized:
                self.conversation.show_error("Usage: muscles chest, triceps")
                return RouteResult("continue")
            event_type = "muscles_updated"
            payload = {"exercise_name": draft["name"], "muscles": normalized}
            success_text = "Exercise muscles updated."

        elif command == "cue":
            cue = parsed.payload.get("cue") if parsed.payload else argument
            cue = str(cue or "").strip()
            if not cue:
                self.conversation.show_error("Usage: cue <text>")
                return RouteResult("continue")
            self.exercise_entry.add_cue(draft, cue)
            event_type = "cue_added"
            payload = {"exercise_name": draft["name"], "cue": cue}
            success_text = "Exercise cue added."

        else:  # warmup_note
            text = parsed.payload.get("warmup_note") if parsed.payload else argument
            text = str(text or "").strip()
            if not text:
                self.conversation.show_error("Usage: warmup_note <text>")
                return RouteResult("continue")
            self.exercise_entry.update_warmup_notes(draft, text)
            event_type = "warmup_note_updated"
            payload = {"exercise_name": draft["name"], "warmup_note": text}
            lowered = text.lower()
            if "warmup" in lowered and "set" in lowered:
                success_text = "Warmup plan noted. Tell me the first warmup set like `w 0x10` or `w 20x8`."
            else:
                success_text = "Warmup note updated."

        self.persistence.append_event(session_id, event_type, payload)
        self.state.sync_dialogue_stage_with_draft()
        self.persistence.update_snapshot(self.state.get_session().to_dict(), current_exercise=draft)
        self.conversation.show_success(success_text)
        return RouteResult("continue", prompt_next=True)

    @staticmethod
    def _parse_goal_argument(argument: str) -> dict:
        """
        Parse command-style goal argument.

        Supported examples:
        - 60kg x 3 sets x 8-10
        - 60 x 3 x 8-10 rest 2
        """
        import re

        text = (argument or "").strip().lower()
        if not text:
            return {}

        result = {}
        weight_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*(?:kg)?", text)
        sets_match = re.search(r"([1-9][0-9]*)\s*(?:sets?|x)", text)
        reps_match = re.search(r"([1-9][0-9]*)\s*-\s*([1-9][0-9]*)", text)
        rest_match = re.search(r"(?:rest)\s*([0-9]+)", text)

        if weight_match:
            result["weight"] = float(weight_match.group(1))
        if sets_match:
            result["sets"] = int(sets_match.group(1))
        if reps_match:
            result["rep_min"] = int(reps_match.group(1))
            result["rep_max"] = int(reps_match.group(2))
        if rest_match:
            result["rest_minutes"] = int(rest_match.group(1))
        return result
