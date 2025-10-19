"""
Data models for training logs.

This module defines the core data structures and classes for representing
training session data according to the NoSQL JSONC schema.
"""

from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
import json
from enum import Enum

from .validators import TrainingLogValidator
from .exceptions import TrainingLogValidationError


def _clean_none_and_empty(obj: Any) -> Any:
    """Recursively remove None values and empty lists from dictionaries and lists.

    This enforces the policy to omit empty lists from serialized output.
    """
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            cleaned = _clean_none_and_empty(v)
            if cleaned is None:
                continue
            if isinstance(cleaned, list) and len(cleaned) == 0:
                continue
            result[k] = cleaned
        return result
    if isinstance(obj, list):
        cleaned_list = [_clean_none_and_empty(v) for v in obj]
        cleaned_list = [v for v in cleaned_list if v is not None]
        return cleaned_list
    return obj


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
    # partial reps are numeric and default to 0 when not provided. Use int to avoid None-related comparisons.
    partial: int = 0
    
    def __post_init__(self):
        """Validate rep count data after initialization."""
        if self.full < 0:
            raise TrainingLogValidationError("Full reps cannot be negative")
        if self.partial is None:
            # Coerce None -> 0 for robustness, but prefer callers to provide int.
            self.partial = 0
        if self.partial < 0:
            raise TrainingLogValidationError("Partial reps cannot be negative")
    
    @property
    def total_reps(self) -> int:
        """Total repetitions including partial reps."""
        return int(self.full) + int(self.partial)

    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary representation."""
        return {"full": self.full, "partial": self.partial}
    
    @classmethod
    def from_dict(cls, data: Union[Dict[str, int], None]) -> Optional['RepCount']:
        """
        Create RepCount from dictionary or None.
        
        Args:
            data: Dictionary with 'full' and 'partial' keys, or None
            
        Returns:
            RepCount instance or None if data is None
        """
        if data is None:
            return None
        return cls(full=data["full"], partial=data.get("partial", 0))

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
    
    def __post_init__(self):
        """Validate rep range data after initialization."""
        if self.min <= 0:
            raise TrainingLogValidationError("Minimum reps must be positive")
        if self.max <= 0:
            raise TrainingLogValidationError("Maximum reps must be positive")
        if self.min > self.max:
            raise TrainingLogValidationError("Minimum reps cannot be greater than maximum reps")
    
    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary representation."""
        return {"min": self.min, "max": self.max}
    
    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> 'RepRange':
        """Create RepRange from dictionary."""
        return cls(min=data["min"], max=data["max"])

MAX_REST_INTERVAL_MINUTES = 15
@dataclass
class Goal:
    """
    Represents the planned goal for an exercise.
    
    This class defines the structured goal for an exercise including
    weight, sets, rep range, and rest time. Used for comparison
    against actual performance.
    
    Attributes:
        weight_kg: Target weight in kilograms (float, required)
        sets: Number of sets to perform (int, required)
        rep_range: Rep range with min and max values (RepRange, required)
        rest_minutes: Rest time between sets in minutes (Optional[int])
    """
    # weight_kg can be zero for bodyweight exercises
    weight_kg: float # add resistancy_type = "resistance band", "bodyweight", etc. in future
    sets: int
    rep_range: RepRange
    rest_minutes: Optional[int] = None # rest_minutes can be None if not specified, for example in learning a new movement or exercise
    
    def __post_init__(self):
        """Validate workout goal data after initialization."""
        if self.weight_kg < 0: 
            raise TrainingLogValidationError("Weight must be positive or zero for bodyweight")
        if self.sets <= 0:
            raise TrainingLogValidationError("Number of sets must be positive")
        if self.rest_minutes  and self.rest_minutes < 0 and self.rest_minutes > MAX_REST_INTERVAL_MINUTES:
            # TODO: add more logic to raise specific validation error messages for > MAX_REST_INTERVAL_MINUTES
            raise TrainingLogValidationError("Invalid rest minutes value")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation using snake_case keys."""
        return _clean_none_and_empty({
            "weight_kg": self.weight_kg,
            "sets": self.sets,
            "rep_range": self.rep_range.to_dict(),
            "rest_minutes": self.rest_minutes,
        })
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Goal':
        """Create Goal from dictionary."""
        # Accept both snake_case and camelCase input for compatibility
        weight = data.get("weight_kg", data.get("weightKg"))
        rep_range_data = data.get("rep_range", data.get("repRange"))
        rest = data.get("rest_minutes", data.get("restMinutes"))
        return cls(
            weight_kg=weight,
            sets=data.get("sets", data.get("sets")),
            rep_range=RepRange.from_dict(rep_range_data),
            rest_minutes=rest
        )


class FailureTechniqueType(Enum):
    """Enumerates supported failure technique types."""
    MYO_REPS = "MyoReps"
    LLP = "LLP"
    STATIC = "StaticHold"
    DROP_SET = "DropSet"


class RepQualityAssessment(Enum):
    """Enumeration for rep quality assessment with canonical values.

    Values are lower-case strings used in JSON representation.
    """
    GOOD = "good"
    BAD = "bad"
    PERFECT = "perfect"
    LEARNING = "learning"

    @staticmethod
    def from_string(value: Union[str, None]) -> Optional["RepQualityAssessment"]:
        """Parse a string (case-insensitive) into a RepQualityAssessment enum.

        Returns None if value is None.
        Raises TrainingLogValidationError if parsing fails.
        """
        if value is None:
            return None
        if isinstance(value, RepQualityAssessment):
            return value
        try:
            normalized = str(value).strip().lower()
        except Exception:
            raise TrainingLogValidationError(f"Invalid rep quality value: {value}")
        for member in RepQualityAssessment:
            if member.value == normalized:
                return member
        raise TrainingLogValidationError(f"Unknown rep quality assessment: {value}")

@dataclass
class MyoRep:
    """Represents a single MyoRep mini-set with number and rep count."""
    number: int
    rep_count: RepCount

    def __post_init__(self):
        if not isinstance(self.number, int) or self.number <= 0:
            raise TrainingLogValidationError("MyoRep.number must be a positive integer")
        if not isinstance(self.rep_count, RepCount):
            raise TrainingLogValidationError("MyoRep.rep_count must be a RepCount")

    def to_dict(self) -> Dict[str, Any]:
        # already snake_case
        return {"number": self.number, "rep_count": self.rep_count.to_dict()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MyoRep':
        return cls(
            number=data["number"],
            rep_count=RepCount.from_dict(data.get("rep_count"))
        )
    
@dataclass
class MyoRepDetails:
    """
    Details for MyoReps technique.
    
    Attributes:
        mini_sets: List[MyoRep] each with keys 'number' (int), 'rep_count' (RepCount)
    """
    mini_sets: List[MyoRep]

    def __post_init__(self):
        # Accept either a list of MyoRep instances or a list of dicts describing MyoRep
        if not isinstance(self.mini_sets, list):
            raise TrainingLogValidationError("mini_sets must be a list")
        normalized: List[MyoRep] = []
        for entry in self.mini_sets:
            if isinstance(entry, MyoRep):
                normalized.append(entry)
                continue
            if isinstance(entry, dict):
                # convert dict to MyoRep (will validate via MyoRep.from_dict)
                normalized.append(MyoRep.from_dict(entry))
                continue
            raise TrainingLogValidationError("Each mini-set entry must be a MyoRep instance or a dict")

        # assign back normalized list of MyoRep objects
        self.mini_sets = normalized

    def to_dict(self) -> Dict[str, Any]:
        # Return a serializable structure using snake_case
        return _clean_none_and_empty({
            "mini_sets": [
                {
                    "number": mr.number,
                    "rep_count": (mr.rep_count.to_dict() if isinstance(mr.rep_count, RepCount) else mr.rep_count),
                }
                for mr in self.mini_sets
            ]
        })

    @classmethod
    def from_dict(cls, data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> 'MyoRepDetails':
        # Accept either a list of mini-set dicts or a dict with key 'mini_sets'
        if isinstance(data, dict):
            # support camelCase 'miniSets' as well
            raw_list = data.get("mini_sets", data.get("miniSets", []))
        else:
            raw_list = data

        mini_reps: List[MyoRep] = []
        for item in raw_list:
            if isinstance(item, MyoRep):
                mini_reps.append(item)
            elif isinstance(item, dict):
                # MyoRep.from_dict will validate and convert
                mini_reps.append(MyoRep.from_dict(item))
            else:
                raise TrainingLogValidationError("Each mini set item must be a dict or MyoRep")

        return cls(mini_sets=mini_reps)


@dataclass
class LLPDetails:
    """Details for LLP technique."""
    partial_rep_count: int

    def __post_init__(self):
        if self.partial_rep_count < 0:
            raise TrainingLogValidationError("partialRepCount cannot be negative")

    def to_dict(self) -> Dict[str, Any]:
        return {"partial_rep_count": self.partial_rep_count}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LLPDetails':
        return cls(partial_rep_count=data.get("partial_rep_count", data.get("partialRepCount")))


@dataclass
class StaticDetails:
    """Details for Static technique."""
    hold_duration_seconds: int

    def __post_init__(self):
        if self.hold_duration_seconds <= 0:
            raise TrainingLogValidationError("holdDurationSeconds must be positive")

    def to_dict(self) -> Dict[str, Any]:
        return {"hold_duration_seconds": self.hold_duration_seconds}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StaticDetails':
        return cls(hold_duration_seconds=data.get("hold_duration_seconds", data.get("holdDurationSeconds")))

@dataclass
class DropSet:
    """Represents a single drop-set entry with count, weight and rep counts."""
    number: int
    weight_kg: float
    rep_count: RepCount

    def __post_init__(self):
        if not isinstance(self.number, int) or self.number <= 0:
            raise TrainingLogValidationError("DropSet.number must be a positive integer")
        if not isinstance(self.weight_kg, (int, float)) or self.weight_kg < 0:
            raise TrainingLogValidationError("DropSet.weight_kg must be a positive number")
        if not isinstance(self.rep_count, RepCount):
            raise TrainingLogValidationError("DropSet.rep_count must be a RepCount")

    def to_dict(self) -> Dict[str, Any]:
        # DropSet already uses snake_case internally
        return {"number": self.number, "weight_kg": self.weight_kg, "rep_count": self.rep_count.to_dict()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DropSet':
        return cls(
            number=data["number"],
            weight_kg=data.get("weight_kg", data.get("weightKg")),
            rep_count=RepCount.from_dict(data.get("rep_count", data.get("repCount")))
        )

@dataclass
class DropSetDetails:
    """
    Details for DropSet technique.
    
    Attributes:
        drop_sets: List of DropSet entries. Serialization uses snake_case keys.
    """
    drop_sets: List[DropSet]

    def __post_init__(self):
        if not isinstance(self.drop_sets, list):
            raise TrainingLogValidationError("DropSet entries must be a list")
        normalized: List[DropSet] = []
        for entry in self.drop_sets:
            if isinstance(entry, dict):
                normalized.append(DropSet.from_dict(entry))
            elif isinstance(entry, DropSet):
                normalized.append(entry)
            else:
                raise TrainingLogValidationError("Each DropSet entry must be a dict or DropSet")
        # assign back to ensure internal consistency
        self.drop_sets = normalized

    def to_dict(self) -> List[Dict[str, Any]]:
        # return a dict wrapper for clarity and consistent naming
        return {"drop_sets": [e.to_dict() for e in self.drop_sets]}

    @classmethod
    def from_dict(cls, data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> 'DropSetDetails':
        if isinstance(data, dict):
            # accept both 'drop_sets' and camelCase 'dropSets'
            raw_entries = data.get("drop_sets", data.get("dropSets", []))
        else:
            raw_entries = data
        drop_sets = [DropSet.from_dict(e) if isinstance(e, dict) else e for e in raw_entries]
        return cls(drop_sets=drop_sets)


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

    def __post_init__(self):
        # Nothing extra here; each detail class validates itself
        if not isinstance(self.technique_type, FailureTechniqueType):
            raise TrainingLogValidationError("technique_type must be a FailureTechniqueType")

    def to_dict(self) -> Dict[str, Any]:
        raw_details: Any
        if isinstance(self.details, MyoRepDetails):
            raw_details = self.details.to_dict()
        elif isinstance(self.details, LLPDetails):
            raw_details = self.details.to_dict()
        elif isinstance(self.details, StaticDetails):
            raw_details = self.details.to_dict()
        elif isinstance(self.details, DropSetDetails):
            raw_details = self.details.to_dict()
        else:
            raise TrainingLogValidationError("Unsupported failure technique details type")

        # Return with canonical enum label and details (details bodies use snake_case)
        return {"type": self.technique_type.value, "details": raw_details}

    @staticmethod
    def _parse_type_case_insensitive(type_value: str) -> FailureTechniqueType:
        # Accept known aliases case-insensitively
        normalized = (type_value or "").strip().lower()
        mapping = {
            # MyoReps alias variants
            "myo_reps": FailureTechniqueType.MYO_REPS,
            "myoreps": FailureTechniqueType.MYO_REPS,
            "myo-reps": FailureTechniqueType.MYO_REPS,
            "myo-repcount": FailureTechniqueType.MYO_REPS,
            "myo-rep-count": FailureTechniqueType.MYO_REPS,
            # LLP alias variants
            "llp": FailureTechniqueType.LLP,
            "low-level-plateau": FailureTechniqueType.LLP,
            # Static hold
            "static": FailureTechniqueType.STATIC,
            "statichold": FailureTechniqueType.STATIC,
            "static_hold": FailureTechniqueType.STATIC,
            "static-hold": FailureTechniqueType.STATIC,
            # Drop set variants
            "dropset": FailureTechniqueType.DROP_SET,
            "drop_set": FailureTechniqueType.DROP_SET,
            "drop-set": FailureTechniqueType.DROP_SET,
        }
        if normalized in mapping:
            return mapping[normalized]
        # Fallback: try exact enum value labels
        for enum_member in FailureTechniqueType:
            if enum_member.value.strip().lower() == normalized:
                return enum_member
        raise TrainingLogValidationError(f"Unknown failure technique type: {type_value}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FailureTechnique':
        tech_type = cls._parse_type_case_insensitive(data["type"])  # case-insensitive
        details_raw = data.get("details")
        if tech_type is FailureTechniqueType.MYO_REPS:
            details = MyoRepDetails.from_dict(details_raw if isinstance(details_raw, dict) else {"mini_sets": []})
        elif tech_type is FailureTechniqueType.LLP:
            details = LLPDetails.from_dict(details_raw)
        elif tech_type is FailureTechniqueType.STATIC:
            details = StaticDetails.from_dict(details_raw)
        elif tech_type is FailureTechniqueType.DROP_SET:
            details = DropSetDetails.from_dict(details_raw if details_raw is not None else [])
        else:
            raise TrainingLogValidationError("Unsupported failure technique type")
        return cls(technique_type=tech_type, details=details)


@dataclass
class WarmupSet:
    """
    Represents a warm-up set performed before working sets.
    
    This class handles warm-up set data including set number, weight,
    rep count (which can be null for "feel" based sets), and optional notes.
    
    Attributes:
        number: Set number (int, required)
        weight_kg: Weight in kilograms (float, required)
        rep_count: Number of reps, can be None for "feel" based sets (Optional[int]) # repCount cannot have partial reps here, but can be calculated for pyramid warmups
        notes: Optional notes for this set (Optional[str])
    """
    number: int
    weight_kg: float # include resistancy_type = "resistance band", "bodyweight", etc. in future
    rep_count: Optional[int] = None
    notes: Optional[str] = None
    
    def __post_init__(self):
        """Validate warm-up set data after initialization."""
        if self.number <= 0:
            raise TrainingLogValidationError("Set number must be positive")
        if self.weight_kg < 0:
            raise TrainingLogValidationError("Weight must be positive or zero for bodyweight")
        if self.rep_count is not None and self.rep_count < 0:
            raise TrainingLogValidationError("Rep count cannot be negative")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return _clean_none_and_empty({
            "set": self.number,
            "weight_kg": self.weight_kg,
            "rep_count": self.rep_count,
            "notes": self.notes,
        })
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WarmupSet':
        """Create WarmupSet from dictionary."""
        return cls(
            number=data["set"],
            weight_kg=data.get("weight_kg", data.get("weightKg")),
            rep_count=data.get("rep_count", data.get("repCount")),
            notes=data.get("notes")
        )


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
        rpe: Rating of Perceived Exertion 1-10 (Optional[float]). May be an integer or a half-step (e.g. 7.0 or 7.5). None can be used to indicate that the RPE is not yet set, or we are learning, or deload week etc.
        rep_quality_assessment: Quality of reps - 'bad', 'good', 'perfect' or 'learning' (Optional[str]), None simply means not recorded
        actual_rest_minutes: Actual rest time before this set (Optional[int]), to cover scenarios where the rest time was longer than planned, None simply means not recorded
        notes: Optional notes for this set (Optional[str])
        failure_technique: Optional failure technique used (Optional[FailureTechnique])
    """
    number: int
    weight_kg: float # include resistancy_type = "resistance band", "bodyweight", etc. in future
    rep_count: RepCount
    rpe: Optional[float] = None ## None can be used to indicate that the RPE is not yet set, or we are learning, or deload week etc.
    rep_quality_assessment: Optional[RepQualityAssessment] = None # None simply means not recorded
    actual_rest_minutes: Optional[int] = None
    notes: Optional[str] = None
    failure_technique: Optional[FailureTechnique] = None
    
    def __post_init__(self):
        """Validate working set data after initialization."""
        if self.number <= 0:
            raise TrainingLogValidationError("Set number must be positive")
        if self.weight_kg < 0:
            raise TrainingLogValidationError("Weight must be positive or zero for bodyweight")
        # rpe and rep_quality_assessment are required in schema context, but may be None when not set yet
        if self.rpe is not None:
            TrainingLogValidator.validate_rpe(self.rpe)
        if self.rep_quality_assessment is not None:
            # If a string was passed in (some callers might bypass from_dict), convert it.
            if isinstance(self.rep_quality_assessment, str):
                self.rep_quality_assessment = RepQualityAssessment.from_string(self.rep_quality_assessment)
            elif not isinstance(self.rep_quality_assessment, RepQualityAssessment):
                raise TrainingLogValidationError("rep_quality_assessment must be a RepQualityAssessment or string")
        
        if self.actual_rest_minutes is not None and self.actual_rest_minutes < 0 and self.actual_rest_minutes > MAX_REST_INTERVAL_MINUTES:
            raise TrainingLogValidationError("Invalid actual rest minutes value")
        
        # Failure technique should only be present for RPE 10 sets
        if self.failure_technique is not None:
            if self.rpe is None or self.rpe != 10:
                raise TrainingLogValidationError("Failure technique can only be used with RPE 10 sets")

        # Ensure rep_count is present and valid
        if not isinstance(self.rep_count, RepCount):
            raise TrainingLogValidationError("rep_count is required and must be a RepCount instance")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return _clean_none_and_empty({
            "set": self.number,
            "weight_kg": self.weight_kg,
            "rep_count": self.rep_count.to_dict(),
            "rpe": self.rpe,
            "rep_quality": (self.rep_quality_assessment.value if isinstance(self.rep_quality_assessment, RepQualityAssessment) else None),
            "actual_rest_minutes": self.actual_rest_minutes,
            "notes": self.notes,
            "failure_technique": self.failure_technique.to_dict() if self.failure_technique is not None else None,
        })
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkingSet':
        """Create WorkingSet from dictionary."""
        failure_technique = None
        # accept both camelCase and snake_case
        if "failureTechnique" in data or "failure_technique" in data:
            failure_raw = data.get("failureTechnique", data.get("failure_technique"))
            failure_technique = FailureTechnique.from_dict(failure_raw)
        rep_count_obj = RepCount.from_dict(data.get("rep_count", data.get("repCount")))
        if rep_count_obj is None:
            raise TrainingLogValidationError("WorkingSet.repCount is required")

        return cls(
            number=data["set"],
            weight_kg=data.get("weight_kg", data.get("weightKg")),
            rep_count=rep_count_obj,
            rpe=data.get("rpe"),
            rep_quality_assessment=data.get("rep_quality", data.get("repQuality")),
            actual_rest_minutes=data.get("actual_rest_minutes", data.get("actualRestMinutes")),
            notes=data.get("notes"),
            failure_technique=failure_technique
        )


@dataclass
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
        working_sets: List of working sets (Optional[List[WorkingSet]])
        target_muscle_groups: List of muscle groups targeted (Optional[List[str]])
        rep_tempo: Tempo string in format "eccentric-pause-concentric-pause" (Optional[str])
        current_goal: Planned goal for this exercise (Optional[Goal])
        warmup_sets: List of warm-up sets (Optional[List[WarmupSet]])
        notes: General notes for the exercise (Optional[str])
        warmup_notes: Notes specific to warm-up (Optional[str])
        form_cues: List of form cues (Optional[List[str]])
    """
    number: int
    name: str
    working_sets: List[WorkingSet] = None # to show that a new movement was included in the session, being learned, but no working sets were performed yet
    target_muscle_groups: Optional[List[str]] = None
    rep_tempo: Optional[str] = None
    current_goal: Optional[Goal] = None
    warmup_sets: Optional[List[WarmupSet]] = None
    notes: Optional[str] = None
    warmup_notes: Optional[str] = None
    form_cues: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return _clean_none_and_empty({
            "number": self.number,
            "name": self.name,
            "current_goal": self.current_goal.to_dict() if self.current_goal is not None else None,
            "warmup_sets": [w.to_dict() for w in self.warmup_sets] if self.warmup_sets else None,
            "working_sets": [w.to_dict() for w in self.working_sets] if self.working_sets else None,
            "notes": self.notes,
            "warmup_notes": self.warmup_notes,
            "form_cues": self.form_cues,
        })

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Exercise':
        # accept both snake_case and camelCase
        return cls(
            number=data["number"],
            name=data["name"],
            working_sets=[WorkingSet.from_dict(ws) for ws in data.get("working_sets", data.get("workingSets", []))],
            target_muscle_groups=data.get("target_muscle_groups", data.get("targetMuscleGroups")),
            rep_tempo=data.get("rep_tempo", data.get("repTempo")),
            current_goal=Goal.from_dict(data.get("current_goal", data.get("currentGoal"))) if data.get("current_goal", data.get("currentGoal")) is not None else None,
            warmup_sets=[WarmupSet.from_dict(ws) for ws in data.get("warmup_sets", data.get("warmupSets", []))] if data.get("warmup_sets", data.get("warmupSets")) else None,
            notes=data.get("notes"),
            warmup_notes=data.get("warmup_notes", data.get("warmupNotes")),
            form_cues=data.get("form_cues", data.get("formCues"))
        )


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
        date: Date of training session in YYYY-MM-DD format (str, required)
        program: Name of the training program (str, required)
        program_length_weeks: Total length of the program in weeks (int, required)
        phase: Current 13-week training phase number (int, required)
        week: Week number within current phase ex 1-12 if program_length_weeks is 12 (int, required)
        is_deload_week: Boolean flag for deload weeks (bool, required)
        focus: Primary focus of the training session (str, required)
        exercises: List of exercises performed (List[Exercise], required)
        session_duration_minutes: Total duration in minutes (int, required)
        program_author: Name of the author of the training program (str, required)
    """
    data_model_version: str
    data_model_type: str
    session_id: str
    user_id: str
    user_name: str
    date: str
    program: str
    program_author: str
    program_length_weeks: int
    phase: int
    week: int
    is_deload_week: bool
    focus: str
    exercises: List[Exercise]
    session_duration_minutes: int
    
    def __post_init__(self):
        """Validate training session data after initialization."""
        # Validate required string fields
        for field_name in ["data_model_version", "data_model_type", "session_id", "user_id", "user_name", "program",
                            "program_author", "focus"]:
            value = getattr(self, field_name)
            TrainingLogValidator.validate_string_not_empty(value, field_name)
        
        # Validate date format
        TrainingLogValidator.validate_date_string(self.date)
        
        # Validate program
        TrainingLogValidator.validate_string_not_empty(self.program, "program")
        # Validate program length weeks
        TrainingLogValidator.validate_positive_integer(self.program_length_weeks, "program_length_weeks")
        # Validate phase
        TrainingLogValidator.validate_positive_integer(self.phase, "phase")
        # Validate week within phase (1..program_length_weeks)
        TrainingLogValidator.validate_range(self.week, 1, self.program_length_weeks, "week")
        # Validate session duration
        TrainingLogValidator.validate_positive_integer(self.session_duration_minutes, "session_duration_minutes")
        
        # Validate exercises
        if not isinstance(self.exercises, list):
            raise TrainingLogValidationError("Exercises must be a list")
        
        # Validate exercise number is sequential
        for i, exercise in enumerate(self.exercises):
            if exercise.number != i + 1:
                raise TrainingLogValidationError(
                    f"Exercise number must be sequential, expected {i + 1}, got {exercise.number}"
                )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        # Emit snake_case for all external-facing fields
        return {
            "data_model_version": self.data_model_version,
            "data_model_type": self.data_model_type,
            "_id": self.session_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "date": self.date,
            "phase": self.phase,
            "week": self.week,
            "is_deload_week": self.is_deload_week,
            "focus": self.focus,
            "exercises": [exercise.to_dict() for exercise in self.exercises],
            "session_duration_minutes": self.session_duration_minutes,
            "program": self.program,
            "program_length_weeks": self.program_length_weeks,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TrainingSession':
        """Create TrainingSession from dictionary."""
        # Accept both snake_case and camelCase input
        return cls(
            data_model_version=data.get("data_model_version", data.get("dataModelVersion")),
            data_model_type=data.get("data_model_type", data.get("dataModelType")),
            session_id=data.get("_id", data.get("_id")),
            user_id=data.get("user_id", data.get("userId")),
            user_name=data.get("user_name", data.get("userName")),
            date=data.get("date"),
            phase=data.get("phase"),
            week=data.get("week"),
            is_deload_week=data.get("is_deload_week", data.get("isDeloadWeek")),
            focus=data.get("focus"),
            exercises=[Exercise.from_dict(ex) for ex in data.get("exercises", data.get("exercises", []))],
            session_duration_minutes=data.get("session_duration_minutes", data.get("sessionDurationMinutes")),
            program=data.get("program"),
            program_length_weeks=data.get("program_length_weeks", data.get("programLengthWeeks")),
        )
    
    def to_json(self) -> str:
        """Convert to JSON string representation."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_string: str) -> 'TrainingSession':
        """Create TrainingSession from JSON string."""
        data = json.loads(json_string)
        return cls.from_dict(data)
    
    
    def get_exercise_by_name(self, name: str) -> Optional[Exercise]:
        """
        Find an exercise by name.
        
        Args:
            name: Name of the exercise to find
            
        Returns:
            Exercise object if found, None otherwise
        """
        # Case-insensitive comparison; robust to None
        target = (name or "").strip().lower()
        for exercise in self.exercises:
            if (exercise.name or "").strip().lower() == target:
                return exercise
        return None
    
    