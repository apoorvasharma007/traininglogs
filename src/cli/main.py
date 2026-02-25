#!/usr/bin/env python3
"""traininglogs CLI entry point using the modular workflow architecture."""

import sys
from pathlib import Path

# Add src directory to import path for top-level package imports.
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import WorkoutAgent
from ai import ConversationalAIService, LLMInterpreterService, build_llm_provider_from_env
from cli import prompts
from config import settings
from conversation import ConversationResponseService, UserConversationService
from data import (
    DataPersistenceService,
    LiveSessionStore,
    build_cloud_database_repository,
)
from guidance import HistoryGuidanceService
from intake import (
    ExerciseEntryService,
    InputParsingService,
    MetadataService,
    ValidateDataService,
)
from persistence import MigrationManager, TrainingSessionRepository, get_database
from persistence.exporter import SessionExporter
from repository import HybridDataSource
from services import ExerciseService, HistoryService, ProgressionService, SessionService
from state import SessionStateService
from workflow import AgentControllerService, IntentRouterService, SessionWorkflowService


def _build_workflow(db):
    """Build application services and return runnable workflow + LLM status."""
    repo = TrainingSessionRepository(db)

    data_source = HybridDataSource(repo)
    history_service = HistoryService(data_source)
    progression_service = ProgressionService(history_service)
    exercise_service = ExerciseService()
    session_service = SessionService()
    agent = WorkoutAgent(
        history_service,
        progression_service,
        exercise_service,
        session_service,
    )

    llm_provider = build_llm_provider_from_env()
    conversational_ai_service = ConversationalAIService(llm_provider)
    llm_interpreter_service = LLMInterpreterService(conversational_ai_service)

    input_parsing_service = InputParsingService(
        conversational_ai_service=llm_interpreter_service,
    )
    validate_data_service = ValidateDataService()
    metadata_service = MetadataService(input_parsing_service, validate_data_service)
    exercise_entry_service = ExerciseEntryService(validate_data_service)
    history_guidance_service = HistoryGuidanceService(agent)
    response_service = ConversationResponseService(
        conversational_ai_service=llm_interpreter_service
    )
    user_conversation_service = UserConversationService(
        response_service,
        conversational_ai_service=llm_interpreter_service,
    )
    session_state_service = SessionStateService()

    data_persistence_service = DataPersistenceService(
        database_repository=repo,
        json_export_service=SessionExporter(),
        live_session_store=LiveSessionStore(str(settings.OUTPUT_DIR / "live_sessions")),
        cloud_repository=build_cloud_database_repository(),
    )
    intent_router_service = IntentRouterService(
        agent=agent,
        conversation=user_conversation_service,
        exercise_entry=exercise_entry_service,
        history_guidance=history_guidance_service,
        parsing=input_parsing_service,
        validation=validate_data_service,
        state=session_state_service,
        persistence=data_persistence_service,
    )
    agent_controller_service = AgentControllerService(
        conversation=user_conversation_service,
        parsing=input_parsing_service,
        state=session_state_service,
        intent_router=intent_router_service,
    )

    workflow = SessionWorkflowService(
        agent=agent,
        user_conversation_service=user_conversation_service,
        metadata_service=metadata_service,
        session_state_service=session_state_service,
        data_persistence_service=data_persistence_service,
        agent_controller_service=agent_controller_service,
        db_path=settings.get_db_path(),
    )
    return workflow, llm_interpreter_service.status_message()


def main() -> int:
    """Bootstrap dependencies and run the workflow service."""
    print("\n🏋️  traininglogs CLI v1 (Workflow Architecture)")
    print("=" * 50)

    db = None
    try:
        db = get_database(settings.get_db_path())
        db.init_schema()

        migration_mgr = MigrationManager(db)
        if not migration_mgr.check_schema_compatibility():
            print("\n⚠️  Database schema version mismatch.")
            print("   Run: python scripts/init_db.py")
            return 1

        workflow, llm_status = _build_workflow(db)
        prompts.show_info(llm_status)
        return workflow.run()

    except KeyboardInterrupt:
        print("\n\n⏸️  Interrupted by user.")
        return 0
    except Exception as err:
        prompts.show_error(str(err))
        if settings.DEBUG:
            import traceback

            traceback.print_exc()
        return 1
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
