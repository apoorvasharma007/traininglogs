"""End-to-end workout flow orchestration service."""

class SessionWorkflowService:
    """Drive full app workflow from metadata intake to final persistence."""

    RESTART_EXIT_CODE = 90

    def __init__(
        self,
        agent,
        user_conversation_service,
        metadata_service,
        session_state_service,
        data_persistence_service,
        agent_controller_service,
        db_path: str,
    ):
        self.agent = agent
        self.conversation = user_conversation_service
        self.metadata = metadata_service
        self.state = session_state_service
        self.persistence = data_persistence_service
        self.controller = agent_controller_service
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
        self.conversation.show_info(
            "Great, your session is ready. Tell me the first exercise (for example: 'let's do bench press')."
        )
        self.conversation.show_info(
            "You can say things naturally. Type `help` anytime for command syntax."
        )

        while True:
            raw = self.conversation.prompt_command()
            turn = self.controller.handle_user_turn(raw, restart_exit_code=self.RESTART_EXIT_CODE)
            if turn.outcome == "continue":
                continue
            if turn.outcome == "restart":
                return self.RESTART_EXIT_CODE
            if turn.outcome == "finish":
                return self._finalize_session(self.state.get_session())
            return turn.exit_code

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
