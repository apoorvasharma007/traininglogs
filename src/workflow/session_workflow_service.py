"""End-to-end workout flow orchestration service."""

from typing import Any, Dict, Optional

from core.validators import ValidationError


class SessionWorkflowService:
    """Drive full app workflow from metadata intake to final persistence."""

    RESTART_EXIT_CODE = 90

    def __init__(
        self,
        agent,
        user_conversation_service,
        metadata_service,
        exercise_entry_service,
        history_guidance_service,
        input_parsing_service,
        validate_data_service,
        session_state_service,
        data_persistence_service,
        db_path: str,
    ):
        self.agent = agent
        self.conversation = user_conversation_service
        self.metadata = metadata_service
        self.exercise_entry = exercise_entry_service
        self.history_guidance = history_guidance_service
        self.parsing = input_parsing_service
        self.validation = validate_data_service
        self.state = session_state_service
        self.persistence = data_persistence_service
        self.db_path = db_path

    def run(self) -> int:
        """Run the full session workflow."""
        while True:
            started = self._start_or_resume_session()
            if not started:
                return 0

            result = self._run_conversational_loop()
            if result == self.RESTART_EXIT_CODE:
                continue
            return result

    def _start_or_resume_session(self) -> bool:
        """Either recover latest snapshot or start a fresh session."""
        resume_snapshot = self.persistence.get_latest_resumable_snapshot()
        if resume_snapshot and self.conversation.confirm_action("Resume your last in-progress session?"):
            session, draft = self.state.restore_from_snapshot(resume_snapshot)
            self.conversation.show_info(
                f"Resumed session {session.id[:8]} with {len(session.exercises)} committed exercises."
            )
            if draft:
                self.conversation.show_info(
                    f"Recovered draft: {draft.get('name')} "
                    f"(w={len(draft.get('warmup_sets', []))}, "
                    f"s={len(draft.get('working_sets', []))})"
                )
            self.persistence.append_event(
                session.id,
                "session_resumed",
                {"exercise_count": len(session.exercises), "has_draft": bool(draft)},
            )
            return True

        metadata_dict = self.conversation.collect_metadata(self.metadata)
        if metadata_dict is None:
            self.conversation.show_info("Session setup cancelled.")
            return False
        metadata_contract = self.metadata.to_contract(metadata_dict)
        session = self.state.start_session(self.agent, metadata_contract)
        self.conversation.show_info(f"Session started: {session.id[:8]}...")
        self.persistence.begin_session(session.to_dict())
        return True

    def _run_conversational_loop(self) -> int:
        """Run the command and conversational intake loop."""
        self.conversation.show_info("Conversational workout logging active.")
        self.conversation.show_help()
        self.conversation.show_info(
            "Start with an exercise name or command (for example: 'let's do bench press')."
        )
        self.conversation.show_info(
            "Use `finish` to save, `cancel` to discard, and `help` or `/help` anytime."
        )
        self.conversation.show_info(
            "Use `restart` anytime to discard this session and start fresh."
        )

        session = self.state.get_session()

        while True:
            raw = self.conversation.prompt_command()
            draft = self.state.get_draft()

            parsed = self.parsing.parse_workout_input(raw, draft_active=bool(draft))
            if not parsed:
                self.conversation.show_error(
                    "I couldn't parse that input. Type `help` for strict commands, "
                    "or enable LLM mode with TRAININGLOGS_LLM_ENABLED=true for natural language."
                )
                continue

            if parsed.source != "command":
                self.conversation.show_info(f"I understood: {parsed.preview}")
                if not self.conversation.confirm_action("Use this interpretation?"):
                    self.conversation.show_info("No problem. Rephrase the message.")
                    continue
                self.parsing.remember_interpretation(raw, parsed)

            command = parsed.action
            argument = parsed.argument

            if command == "help":
                self.conversation.show_help()
                continue

            if command == "status":
                self.conversation.show_mobile_status(session, draft)
                continue

            if command == "ex":
                exercise_name = parsed.payload.get("exercise_name") if parsed.payload else argument
                if not exercise_name:
                    self.conversation.show_error("Usage: ex <exercise name>")
                    continue
                try:
                    self.validation.validate_exercise_name(exercise_name)
                except ValidationError as err:
                    self.conversation.show_error(str(err))
                    continue

                if self.exercise_entry.has_sets(draft):
                    if not self.conversation.confirm_action("Discard current draft and start new exercise?"):
                        continue

                context = self.history_guidance.get_logging_context(exercise_name)
                self.conversation.show_history_lines(self.history_guidance.to_concise_lines(context))
                new_draft = self.exercise_entry.create_draft(exercise_name)
                self.state.set_draft(new_draft)

                self.persistence.append_event(
                    session.id,
                    "exercise_started",
                    {"exercise_name": exercise_name},
                )
                self.persistence.update_snapshot(session.to_dict(), current_exercise=new_draft)
                continue

            if command in {"w", "s"}:
                if not draft:
                    self.conversation.show_error("No active draft. Start one with: ex <exercise name>")
                    continue

                set_data = parsed.payload.get("set_data") if parsed.payload else self.parsing.parse_set_argument(argument)
                if not set_data:
                    self.conversation.show_error("Invalid set format. Use: 80x5 or 80x5@8")
                    continue

                is_warmup = command == "w"
                try:
                    normalized = self.validation.normalize_and_validate_set_data(set_data, is_warmup=is_warmup)
                except ValidationError as err:
                    self.conversation.show_error(str(err))
                    continue

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
                self.persistence.update_snapshot(session.to_dict(), current_exercise=draft)
                self.conversation.show_success(
                    f"Added {'warmup' if is_warmup else 'working'} set: "
                    f"{normalized['weight']}kg x {normalized['reps']}"
                )
                continue

            if command == "note":
                if not draft:
                    self.conversation.show_error("No active draft. Start one with: ex <exercise name>")
                    continue
                note_text = parsed.payload.get("note") if parsed.payload else argument
                if not note_text:
                    self.conversation.show_error("Usage: note <text>")
                    continue

                self.exercise_entry.update_note(draft, note_text)
                self.persistence.append_event(
                    session.id,
                    "note_updated",
                    {"exercise_name": draft["name"], "note": note_text},
                )
                self.persistence.update_snapshot(session.to_dict(), current_exercise=draft)
                self.conversation.show_success("Exercise note updated.")
                continue

            if command == "undo":
                if not draft:
                    self.conversation.show_error("No active draft to undo.")
                    continue

                removed, set_type = self.exercise_entry.undo_last_set(draft)
                if removed is None:
                    self.conversation.show_error("Draft has no sets to undo.")
                    continue

                self.persistence.append_event(
                    session.id,
                    "set_removed",
                    {
                        "exercise_name": draft["name"],
                        "set_type": set_type,
                        "set_data": removed,
                    },
                )
                self.persistence.update_snapshot(session.to_dict(), current_exercise=draft)
                self.conversation.show_info("Removed last set from draft.")
                continue

            if command == "done":
                if not draft:
                    self.conversation.show_error("No active draft to commit.")
                    continue

                try:
                    success, error = self.exercise_entry.commit_draft(self.agent, session, draft)
                except ValidationError as err:
                    self.conversation.show_error(str(err))
                    continue

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
                else:
                    self.conversation.show_error(self.agent.get_error_recovery_hints(error))
                continue

            if command == "finish":
                if self.exercise_entry.has_sets(draft):
                    self.conversation.show_error(
                        "You still have an active draft. Use done or ex <new> to discard."
                    )
                    continue
                return self._finalize_session(session)

            if command == "cancel":
                if self.conversation.confirm_action("Cancel session without saving?"):
                    self.persistence.close_session(session.to_dict(), status="cancelled")
                    self.state.reset()
                    self.conversation.show_info("Session cancelled.")
                    return 0
                continue

            if command == "restart":
                if self.conversation.confirm_action("Discard this session and restart from fresh setup?"):
                    self.persistence.close_session(session.to_dict(), status="restarted")
                    self.state.reset()
                    self.conversation.show_info("Restarting from fresh session setup.")
                    return self.RESTART_EXIT_CODE
                continue

            self.conversation.show_error("Unknown command. Type help.")

    def _finalize_session(self, session) -> int:
        """Finalize session and write persistence outcome."""
        if not session.exercises:
            self.conversation.show_info("No exercises added. Session cancelled.")
            self.persistence.close_session(session.to_dict(), status="cancelled_no_exercises")
            self.state.reset()
            return 0

        success, error = self.agent.finalize_workout(session)
        if not success:
            self.conversation.show_error(f"Cannot finalize: {error}")
            return 1

        session_dict = session.to_dict()
        self.conversation.show_summary(session_dict)
        save_requested = self.conversation.confirm_save()

        outcome = self.persistence.persist_final_session(
            session.id,
            session_dict,
            save_requested=save_requested,
        )
        self.conversation.show_persistence_outcome(outcome, db_path=self.db_path)

        if save_requested and not outcome.saved_local:
            return 1
        self.state.reset()
        return 0
