#!/usr/bin/env python3
"""
traininglogs CLI - Interactive workout logging system.

THIN CLI LAYER:
- Only handles I/O (prompts, display)
- All business logic delegated to WorkoutAgent
- Agent coordinates services (history, progression, exercise, session)
- No business logic here!
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from persistence import get_database, MigrationManager, TrainingSessionRepository
from persistence.exporter import SessionExporter
from repository import HybridDataSource
from services import HistoryService, ProgressionService, ExerciseService, SessionService
from agent import WorkoutAgent
from cli import prompts


def main():
    """Main CLI loop - thin I/O layer."""
    print("\n🏋️  traininglogs CLI v1 (Redesigned Architecture)")
    print("=" * 50)
    
    try:
        # === INITIALIZATION (Setup, not business logic) ===
        db = get_database(settings.get_db_path())
        db.init_schema()
        
        migration_mgr = MigrationManager(db)
        if not migration_mgr.check_schema_compatibility():
            print("\n⚠️  Database schema version mismatch.")
            print("   Run: python scripts/init_db.py")
            return 1
        
        # Build data source and services
        db_repo = TrainingSessionRepository(db)
        data_source = HybridDataSource(db_repo)
        
        # Create services
        history_service = HistoryService(data_source)
        progression_service = ProgressionService(history_service)
        exercise_service = ExerciseService()
        session_service = SessionService()
        
        # Create agent - the brain of the app
        agent = WorkoutAgent(
            history_service,
            progression_service,
            exercise_service,
            session_service
        )
        
        exporter = SessionExporter()
        
        # === WORKOUT WORKFLOW (Orchestrated by Agent) ===
        metadata = prompts.prompt_session_metadata()
        session = agent.prepare_workout_session(
            phase=metadata["phase"],
            week=metadata["week"],
            focus=metadata["focus"],
            is_deload=metadata["is_deload"]
        )
        
        prompts.show_info(f"Session started: {session.id[:8]}...")
        
        # Exercise logging loop
        exercise_count = 1
        while True:
            choice = prompts.prompt_continue_session()
            
            if choice == 'f':  # Finish session
                break
            elif choice == 'c':  # Cancel
                prompts.show_info("Session cancelled.")
                return 0
            elif choice == 'a' or choice == '':  # Add exercise (default)
                exercise_name = prompts.prompt_exercise_name(exercise_count)
                
                # Agent prepares context (queries history, suggests progression)
                context = agent.prepare_exercise_logging(exercise_name)
                
                # Show context to user (smart prompting!)
                prompts.show_exercise_context(context)
                
                # Get warmup and working sets from user
                warmup_sets = prompts.prompt_sets(
                    "warmup",
                    suggested_count=2,
                    suggested_weight=context.suggested_weight
                )
                working_sets = prompts.prompt_sets(
                    "working",
                    suggested_count=1,
                    suggested_weight=context.suggested_weight,
                    suggested_reps_range=context.suggested_reps_range
                )
                
                # Agent validates and adds to session
                success, error = agent.log_exercise(
                    session,
                    exercise_name,
                    warmup_sets,
                    working_sets
                )
                
                if success:
                    exercise_count += 1
                    prompts.show_success(f"✅ Added: {exercise_name}")
                else:
                    # Agent provides smart error recovery
                    hint = agent.get_error_recovery_hints(error)
                    prompts.show_error(hint)
                    retry = prompts.confirm_action("Try again?")
                    if not retry:
                        continue
                    # Loop will ask for exercise again
            else:
                prompts.show_info("Invalid choice. Please try again.")
        
        # === SESSION FINALIZATION (via Agent) ===
        success, error = agent.finalize_workout(session)
        if not success:
            prompts.show_error(f"Cannot finalize: {error}")
            return 1
        
        if len(session.exercises) > 0:
            prompts.show_session_summary(session.to_dict())
            
            if prompts.confirm_save():
                # Save to database and export JSON
                db_repo.save_session(session.id, session.to_dict())
                exporter.export_session(session.to_dict())
                
                prompts.show_success("Session saved! ✅")
                prompts.show_info("Files written:")
                prompts.show_info("  • Database: traininglogs.db")
                prompts.show_info("  • JSON file: data/output/sessions/training_session_*.json")
            else:
                prompts.show_info("Session not saved.")
        else:
            prompts.show_info("No exercises added. Session cancelled.")
        
        db.close()
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⏸️  Interrupted by user.")
        return 0
    except Exception as e:
        prompts.show_error(str(e))
        if settings.DEBUG:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
