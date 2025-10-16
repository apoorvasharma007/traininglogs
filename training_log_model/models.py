"""
Data models for training logs.

This module defines the core data structures and classes for representing
training session data according to the NoSQL JSONC schema.
"""

from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum

@dataclass
class RepCount:
    """
    Represents rep count data with support for full and partial reps.
    
    This class handles the rep count structure where reps can be tracked
    as full reps, partial reps, or both. Used in working sets to distinguish
    between complete reps and partial reps when going beyond failure.
    
    Attributes:
        full: Number of complete reps performed (int, required)
        partial: Number of partial reps performed (Optional[int], defaults to 0)
    """
    full: int
    partial: Optional[int] = 0

@dataclass
class RepRange:
    """
    Represents a range of reps for workout goals.
    
    This class defines the minimum and maximum number of reps
    that should be performed for a given exercise set.
    
    Attributes:
        min: Minimum number of reps (int, required)
        max: Maximum number of reps (int, required)
    """
    min: int
    max: int

@dataclass
class ExerciseGoal:
    """
    Represents the planned goal for an exercise.
    
    This class defines the structured goal for an exercise including
    weight, sets, rep range, and rest time. Used for comparison
    against actual performance.
    
    Attributes:
        weight_kg: Target weight in kilograms (float, required)
        sets: Number of sets to perform (int, required)
        rep_range: Rep range with min and max values (RepRange, required)
        rest_minutes: Rest time between sets in minutes (int, required)
    """
    weight_kg: float
    sets: int
    rep_range: RepRange
    rest_minutes: int

class FailureTechniqueType(Enum):
    """Enumerates supported failure technique types."""
    MYO_REPS = "MyoReps"
    LLP = "LLP"
    STATIC = "StaticHold"
    DROP_SET = "DropSet"


@dataclass
class MyoRepDetails:
    """
    Details for MyoReps technique.
    
    Attributes:
        mini_sets: List of dictionaries with keys 'miniSet' (int) and 'repCount' (RepCount)
    """
    mini_sets: List[Dict[str, RepCount]]

@dataclass
class LLPDetails:
    """Details for LLP technique."""
    partial_rep_count: int

@dataclass
class StaticDetails:
    """Details for Static technique."""
    hold_duration_seconds: int

@dataclass
class DropSets:
	number: int           # required, > 0
	weightKg: float       # required, > 0
	repCount: RepCount    # required

@dataclass
class DropSetDetails:
    """
    Details for DropSet technique.
    
    Attributes:
        entries: List of dicts each with keys 'number' (int), 'weightKg' (float), 'repCount' (RepCount)
    """
    entries: List[DropSets]

FailureDetails = Union[MyoRepDetails, LLPDetails, StaticDetails, DropSetDetails]

@dataclass
class FailureTechnique:
    """
    Represents an advanced technique used to push past initial failure.
    
    technique_type: FailureTechniqueType (case-insensitive parsing from input)
    details: One of the supported detail classes depending on technique type
    """
    technique_type: FailureTechniqueType
    details: FailureDetails

@dataclass
class WarmupSet:
    """
    Represents a warm-up set performed before working sets.
    
    This class handles warm-up set data including set number, weight,
    rep count (which can be null for "feel" based sets), and optional notes.
    
    Attributes:
        number: Set number (int, required)
        weight_kg: Weight in kilograms (float, required)
        rep_count: Number of reps, can be None for "feel" based sets (Optional[int])
        notes: Optional notes for this set (Optional[str])
    """
    number: int
    weight_kg: float # include resistancy_type = "resistance band", "bodyweight", etc. in future
    rep_count: Optional[int] = None
    notes: Optional[str] = None
    
@dataclass
class WorkingSet:
    """
    Represents a working set with actual performance data.
    
    This class contains the core performance data for a set including
    weight, reps, RPE, quality, rest time, and optional failure technique.
    
    Attributes:
        number: Set number (int, required)
        weight_kg: Weight in kilograms (float, required)
        rep_count: Rep count with full and partial reps (RepCount, required)
        rpe: Rating of Perceived Exertion 1-10 (int, required), can be null if not set
        rep_quality: Quality of reps - 'bad', 'good', or 'perfect' (str, required), can be null if not set
        actual_rest_minutes: Actual rest time before this set (Optional[int])
        notes: Optional notes for this set (Optional[str])
        failure_technique: Optional failure technique used (Optional[FailureTechnique])
    """
    number: int
    weight_kg: float
    rep_count: RepCount
    rpe: int = None ## required but null if not set
    rep_quality: str = None ## required but null if not set
    actual_rest_minutes: Optional[int] = None
    notes: Optional[str] = None
    failure_technique: Optional[FailureTechnique] = None

@dataclass
class Exercise:
    """
    Represents an exercise performed during a training session.
    
    This class contains all data related to a single exercise including
    number, name, muscle groups, tempo, goals, warm-up sets, working sets,
    and various notes and cues.
    
    Attributes:
        number: Order of exercise in the session in which exercise was performed (int, required)
        name: Name of the exercise (str, required)
        target_muscle_groups: List of muscle groups targeted (Optional[List[str]])
        rep_tempo: Tempo string in format "eccentric-pause-concentric-pause" (Optional[str])
        current_goal: Planned goal for this exercise (ExerciseGoal, required), can be null if not set
        warmup_sets: List of warm-up sets (Optional[List[WarmupSet]])
        working_sets: List of working sets (List[WorkingSet], required)
        notes: General notes for the exercise (Optional[str])
        warmup_notes: Notes specific to warm-up (Optional[str])
        form_cues: List of form cues (Optional[List[str]])
    """
    number: int
    name: str
    target_muscle_groups: Optional[List[str]] = None
    rep_tempo: Optional[str] = None
    current_goal: Optional[ExerciseGoal] = None
    warmup_sets: Optional[List[WarmupSet]] = None
    working_sets: List[WorkingSet] = field(default_factory=list)
    notes: Optional[str] = None
    warmup_notes: Optional[str] = None
    form_cues: Optional[List[str]] = None

@dataclass
class TrainingSession:
    """
    Represents a complete training session.
    
    This is the main class that contains all data for a training session
    including metadata, exercises performed, and session duration.
    
    Attributes:
        data_model_version: Version of the data model (str, required)
        data_model_type: Type of data model (str, required)
        session_id: Unique identifier for the session (str, required)
        user_id: Identifier for the user (str, required)
        user_name: User's full name (str, required)
        date: Start date and time in ISO 8601 format (str, required)
        phase: Current 13-week training phase number (int, required)
        week: Week number within current phase 1-13 (int, required)
        is_deload_week: Boolean flag for deload weeks (bool, required)
        focus: Primary focus of the training session (str, required)
        exercises: List of exercises performed (List[Exercise], required)
        session_duration_minutes: Total duration in minutes (int, required)
    """
    data_model_version: str
    data_model_type: str
    session_id: str
    user_id: str
    user_name: str
    date: str
    phase: int
    week: int
    is_deload_week: bool
    focus: str
    exercises: List[Exercise]
    session_duration_minutes: int
    
    # def get_exercise_by_name(self, name: str) -> Optional[Exercise]:
    #     """
    #     Find an exercise by name.
        
    #     Args:
    #         name: Name of the exercise to find
            
    #     Returns:
    #         Exercise object if found, None otherwise
    #     """
    #     # Case-insensitive comparison; robust to None
    #     target = (name or "").strip().lower()
    #     for exercise in self.exercises:
    #         if (exercise.name or "").strip().lower() == target:
    #             return exercise
    #     return None
    
    # def get_exercises_by_muscle_group(self, muscle_group: str) -> List[Exercise]:
    #     """
    #     Find all exercises that target a specific muscle group.
        
    #     Args:
    #         muscle_group: Name of the muscle group to search for
            
    #     Returns:
    #         List of exercises that target the specified muscle group
    #     """
    #     matching_exercises = []
    #     target = (muscle_group or "").strip().lower()
    #     for exercise in self.exercises:
    #         groups = exercise.target_muscle_groups or []
    #         if any((mg or "").strip().lower() == target for mg in groups):
    #             matching_exercises.append(exercise)
    #     return matching_exercises
