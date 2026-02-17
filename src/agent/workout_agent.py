"""
Workout Agent - intelligent orchestrator of the entire workout system.

The agent coordinates all services to provide smart workout logging:
- Queries history for context
- Suggests progression
- Validates exercises
- Handles error recovery
- Orchestrates session flow

This is the single source of workflow logic.
Business logic is in services; UI is in CLI.
Agent bridges the gap with intelligent coordination.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from services.history_service import HistoryService
from services.progression_service import ProgressionService
from services.exercise_service import ExerciseService
from services.session_service import SessionService, Session, SessionMetadata
from core.validators import ValidationError


@dataclass
class LoggingContext:
    """Context for logging an exercise."""
    exercise_name: str
    is_new_exercise: bool
    last_weight: Optional[float]
    max_weight: Optional[float]
    last_date: Optional[str]
    days_since_last: Optional[int]
    suggested_weight: Optional[float]
    suggested_reps_range: Optional[Tuple[int, int]]


@dataclass
class LoggingError:
    """Error during exercise logging with recovery hints."""
    error_type: str  # "validation", "invalid_input", "missing_field"
    message: str
    field: Optional[str]
    suggestions: List[str]  # Hints to fix error


class WorkoutAgent:
    """
    Intelligent agent that orchestrates workout sessions.
    
    Key responsibilities:
    - Guide workout flow (start, add exercises, finish)
    - Make smart suggestions based on history
    - Handle validation and errors gracefully
    - Coordinate all services
    """

    def __init__(
        self,
        history_service: HistoryService,
        progression_service: ProgressionService,
        exercise_service: ExerciseService,
        session_service: SessionService
    ):
        """
        Initialize workout agent.
        
        Args:
            history_service: For querying exercise history
            progression_service: For weight/rep suggestions
            exercise_service: For building exercises
            session_service: For managing sessions
        """
        self.history = history_service
        self.progression = progression_service
        self.exercise = exercise_service
        self.session = session_service

    # Workflow methods

    def prepare_workout_session(
        self,
        phase: str,
        week: int,
        focus: str,
        is_deload: bool = False
    ) -> Session:
        """
        Create a new workout session.
        
        Args:
            phase: Training phase (e.g., "phase 2")
            week: Week number
            focus: Workout focus (e.g., "upper-strength")
            is_deload: Whether this is deload week
            
        Returns:
            New Session object
        """
        metadata = SessionMetadata(
            phase=phase,
            week=week,
            focus=focus,
            is_deload=is_deload
        )

        return self.session.create_session(metadata)

    def prepare_exercise_logging(
        self,
        exercise_name: str
    ) -> LoggingContext:
        """
        Prepare context for logging an exercise.
        
        Queries history, suggests progression, identifies if new exercise.
        Used by CLI to show smart prompts to user.
        
        Args:
            exercise_name: Name of exercise to log
            
        Returns:
            LoggingContext with all context for prompting
        """
        is_new = self.history.is_new_exercise(exercise_name)
        last_ex = self.history.get_last_exercise(exercise_name)
        max_weight = self.history.get_max_weight_achieved(exercise_name)
        days_ago = self.history.days_since_last_attempt(exercise_name)

        last_weight = last_ex.get_max_weight() if last_ex else None

        # Generate suggestion if we have history
        suggested_weight = None
        if last_weight:
            suggestion = self.progression.suggest_next_weight(
                exercise_name,
                last_weight,
                5,  # Assume typical 5 reps for suggestion
                None  # RPE unknown yet
            )
            suggested_weight = suggestion.suggested_weight

        suggested_reps = self.progression.suggest_rep_range(exercise_name)

        return LoggingContext(
            exercise_name=exercise_name,
            is_new_exercise=is_new,
            last_weight=last_weight,
            max_weight=max_weight,
            last_date=last_ex.session_date if last_ex else None,
            days_since_last=days_ago,
            suggested_weight=suggested_weight,
            suggested_reps_range=suggested_reps
        )

    def log_exercise(
        self,
        session: Session,
        exercise_name: str,
        warmup_sets: List[Dict[str, Any]],
        working_sets: List[Dict[str, Any]],
        notes: Optional[str] = None
    ) -> Tuple[bool, Optional[LoggingError]]:
        """
        Log an exercise in a session with smart validation.
        
        Returns:
            (success, error) tuple
            - If success: (True, None)
            - If failed: (False, LoggingError with recovery hints)
        
        Args:
            session: Session to add to
            exercise_name: Exercise name
            warmup_sets: Warmup sets data
            working_sets: Working sets data
            notes: Optional notes
            
        Returns:
            (success, error) tuple
        """
        # Build exercise
        try:
            exercise = self.exercise.build_exercise(
                name=exercise_name,
                warmup_sets=warmup_sets,
                working_sets=working_sets,
                notes=notes
            )
        except ValidationError as e:
            return False, self._create_recovery_error(exercise_name, str(e))

        # Add to session
        try:
            self.session.add_exercise(session, exercise.to_dict())
            return True, None
        except ValidationError as e:
            return False, self._create_recovery_error(exercise_name, str(e))

    def finalize_workout(self, session: Session) -> Tuple[bool, Optional[str]]:
        """
        Finalize session for persistence.
        
        Args:
            session: Session to finalize
            
        Returns:
            (success, error_message) tuple
        """
        try:
            self.session.finalize_session(session)
            return True, None
        except ValidationError as e:
            return False, str(e)

    # Intelligence & suggestions

    def get_next_exercise_suggestions(
        self,
        current_focus: str,
        completed_exercises: List[str],
        limit: int = 3
    ) -> List[str]:
        """
        Suggest what user should log next based on workout focus.
        
        Args:
            current_focus: Workout focus (e.g., "upper-strength")
            completed_exercises: Already logged exercises
            limit: Number of suggestions
            
        Returns:
            List of suggested exercise names
        """
        # Heuristic: typical exercise order by focus
        typical_exercises = {
            "upper-strength": [
                "Barbell Bench Press",
                "Barbell Squat",
                "Barbell Rows",
                "Overhead Press",
                "Lat Pulldown"
            ],
            "lower-strength": [
                "Barbell Squat",
                "Romanian Deadlift",
                "Leg Press",
                "Leg Curls",
                "Leg Extensions"
            ],
            "push-hypertrophy": [
                "Incline Dumbbell Press",
                "Low-to-High Cable Fly",
                "Machine Chest Press",
                "Lateral Raises",
                "Rope Tricep Pushdowns"
            ],
            "pull-hypertrophy": [
                "Incline Bench Rows",
                "Lat Pulldown Machine",
                "Seal Rows",
                "Machine Rows",
                "Face Pulls"
            ],
            "legs-hypertrophy": [
                "Leg Press",
                "Smith Machine Squats",
                "Leg Curls",
                "Leg Extensions",
                "Hack Squats"
            ]
        }

        suggested = typical_exercises.get(current_focus, [])
        available = [
            ex for ex in suggested 
            if ex not in completed_exercises
        ]

        return available[:limit]

    def get_error_recovery_hints(
        self,
        error: LoggingError
    ) -> str:
        """
        Get user-friendly hints for recovering from error.
        
        Args:
            error: LoggingError to recover from
            
        Returns:
            User-friendly hint string
        """
        if not error.suggestions:
            return error.message

        hints = "\n".join([f"• {s}" for s in error.suggestions])
        return f"{error.message}\n\nTry this:\n{hints}"

    # Private helpers

    def _create_recovery_error(
        self,
        exercise_name: str,
        error_message: str
    ) -> LoggingError:
        """Create LoggingError with smart recovery suggestions."""
        suggestions = []

        # Parse error message to provide context-aware suggestions
        if "weight" in error_message.lower():
            last = self.history.get_last_exercise(exercise_name)
            if last:
                weight = last.get_max_weight()
                suggestions.append(f"Last used: {weight}kg")
                suggestions.append(f"Try starting with {weight}kg or less")

        if "reps" in error_message.lower():
            suggested_range = self.progression.suggest_rep_range(exercise_name)
            if suggested_range:
                suggestions.append(
                    f"Try {suggested_range[0]}-{suggested_range[1]} reps"
                )

        if not suggestions:
            suggestions = ["Check the values and try again"]

        return LoggingError(
            error_type="validation",
            message=error_message,
            field=None,
            suggestions=suggestions
        )
