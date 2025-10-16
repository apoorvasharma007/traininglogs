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
        rest_minutes: Rest time between sets in minutes (int, required)
    """
    weight_kg: float # add resistancy_type = "resistance band", "bodyweight", etc. in future
    sets: int
    rep_range: RepRange
    rest_minutes: int
    
    def __post_init__(self):
        """Validate workout goal data after initialization."""
        if self.weight_kg <= 0:
            raise TrainingLogValidationError("Weight must be positive")
        if self.sets <= 0:
            raise TrainingLogValidationError("Number of sets must be positive")
        if self.rest_minutes < 0:
            raise TrainingLogValidationError("Rest minutes cannot be negative")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return _clean_none_and_empty({
            "weightKg": self.weight_kg,
            "sets": self.sets,
            "repRange": self.rep_range.to_dict(),
            "restMinutes": self.rest_minutes,
        })
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Goal':
        """Create Goal from dictionary."""
        return cls(
            weight_kg=data["weightKg"],
            sets=data["sets"],
            rep_range=RepRange.from_dict(data["repRange"]),
            rest_minutes=data["restMinutes"]
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
class MyoRepDetails:
    """
    Details for MyoReps technique.
    
    Attributes:
        mini_sets: List of dictionaries with keys 'miniSet' (int) and 'repCount' (RepCount)
    """
    mini_sets: List[Dict[str, RepCount]]

    def __post_init__(self):
        if not isinstance(self.mini_sets, list):
            raise TrainingLogValidationError("mini_sets must be a list")
        for entry in self.mini_sets:
            if not isinstance(entry, dict):
                raise TrainingLogValidationError("Each mini-set entry must be a dict")
            if "miniSet" not in entry or "repCount" not in entry:
                raise TrainingLogValidationError("Each mini-set must have 'miniSet' and 'repCount'")
            if not isinstance(entry["miniSet"], int):
                raise TrainingLogValidationError("'miniSet' must be an integer")
            rep_count_obj = entry["repCount"]
            if isinstance(rep_count_obj, dict):
                # allow raw dict, validate via RepCount
                rep_count_obj = RepCount.from_dict(rep_count_obj)
                entry["repCount"] = rep_count_obj
            if not isinstance(rep_count_obj, RepCount):
                raise TrainingLogValidationError("'repCount' must be a RepCount or dict")
            if entry["miniSet"] <= 0:
                raise TrainingLogValidationError("miniSet must be positive")

    def to_dict(self) -> Dict[str, Any]:
        return _clean_none_and_empty({
            "miniSets": [
                {
                    "miniSet": ms["miniSet"],
                    "repCount": (
                        ms["repCount"].to_dict() if isinstance(ms["repCount"], RepCount) else ms["repCount"]
                    ),
                }
                for ms in self.mini_sets
            ]
        })

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MyoRepDetails':
        raw_list = data.get("miniSets", [])
        normalized: List[Dict[str, Any]] = []
        for item in raw_list:
            if not isinstance(item, dict):
                raise TrainingLogValidationError("Each miniSet item must be a dict")
            if "repCount" not in item or item.get("repCount") is None:
                raise TrainingLogValidationError("Each miniSet must include a repCount")
            raw_rep = item.get("repCount")
            # Accept either an int (treat as full reps) or a dict for RepCount
            if isinstance(raw_rep, int):
                rep_obj = RepCount(full=raw_rep, partial=0)
            elif isinstance(raw_rep, dict):
                rep_obj = RepCount.from_dict(raw_rep)
                if rep_obj is None:
                    raise TrainingLogValidationError("Invalid repCount in miniSet")
            elif isinstance(raw_rep, RepCount):
                rep_obj = raw_rep
            else:
                raise TrainingLogValidationError("repCount must be an int, dict, or RepCount")
            normalized.append({
                "miniSet": item["miniSet"],
                "repCount": rep_obj,
            })
        return cls(mini_sets=normalized)


@dataclass
class LLPDetails:
    """Details for LLP technique."""
    partial_rep_count: int

    def __post_init__(self):
        if self.partial_rep_count < 0:
            raise TrainingLogValidationError("partialRepCount cannot be negative")

    def to_dict(self) -> Dict[str, Any]:
        return {"partialRepCount": self.partial_rep_count}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LLPDetails':
        return cls(partial_rep_count=data["partialRepCount"])


@dataclass
class StaticDetails:
    """Details for Static technique."""
    hold_duration_seconds: int

    def __post_init__(self):
        if self.hold_duration_seconds <= 0:
            raise TrainingLogValidationError("holdDurationSeconds must be positive")

    def to_dict(self) -> Dict[str, Any]:
        return {"holdDurationSeconds": self.hold_duration_seconds}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StaticDetails':
        return cls(hold_duration_seconds=data["holdDurationSeconds"])

@dataclass
class DropSet:
    """Represents a single drop-set entry with count, weight and rep counts."""
    number: int
    weight_kg: float
    rep_count: RepCount

    def __post_init__(self):
        if not isinstance(self.number, int) or self.number <= 0:
            raise TrainingLogValidationError("DropSet.number must be a positive integer")
        if not isinstance(self.weight_kg, (int, float)) or self.weight_kg <= 0:
            raise TrainingLogValidationError("DropSet.weight_kg must be a positive number")
        if not isinstance(self.rep_count, RepCount):
            raise TrainingLogValidationError("DropSet.rep_count must be a RepCount")

    def to_dict(self) -> Dict[str, Any]:
        return {"number": self.number, "weightKg": self.weight_kg, "repCount": self.rep_count.to_dict()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DropSet':
        return cls(
            number=data["number"],
            weight_kg=data["weightKg"],
            rep_count=RepCount.from_dict(data.get("repCount"))
        )

@dataclass
class DropSetDetails:
    """
    Details for DropSet technique.
    
    Attributes:
        entries: List of dicts each with keys 'number' (int), 'weightKg' (float), 'repCount' (RepCount) # repCount can have partial reps here
    """
    entries: List[DropSet]

    def __post_init__(self):
        if not isinstance(self.entries, list):
            raise TrainingLogValidationError("DropSet entries must be a list")
        normalized: List[DropSet] = []
        for entry in self.entries:
            if isinstance(entry, dict):
                normalized.append(DropSet.from_dict(entry))
            elif isinstance(entry, DropSet):
                normalized.append(entry)
            else:
                raise TrainingLogValidationError("Each DropSet entry must be a dict or DropSet")
        # assign back to ensure internal consistency
        self.entries = normalized

    def to_dict(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.entries]

    @classmethod
    def from_dict(cls, data: Union[List[Dict[str, Any]], Dict[str, Any]]) -> 'DropSetDetails':
        if isinstance(data, dict):
            raw_entries = data.get("entries", [])
        else:
            raw_entries = data
        entries = [DropSet.from_dict(e) if isinstance(e, dict) else e for e in raw_entries]
        return cls(entries=entries)


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
            details = MyoRepDetails.from_dict(details_raw if isinstance(details_raw, dict) else {"miniSets": []})
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
        if self.weight_kg <= 0:
            raise TrainingLogValidationError("Weight must be positive")
        if self.rep_count is not None and self.rep_count < 0:
            raise TrainingLogValidationError("Rep count cannot be negative")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return _clean_none_and_empty({
            "set": self.number,
            "weightKg": self.weight_kg,
            "repCount": self.rep_count,
            "notes": self.notes,
        })
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WarmupSet':
        """Create WarmupSet from dictionary."""
        return cls(
            number=data["set"],
            weight_kg=data["weightKg"],
            rep_count=data.get("repCount"),
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
        rpe: Rating of Perceived Exertion 1-10 (Optional[int]), None can be used to indicate that the RPE is not yet set, or we are learning, or deload week etc.
        rep_quality_assessment: Quality of reps - 'bad', 'good', 'perfect' or 'learning' (Optional[str]), None simply means not recorded
        actual_rest_minutes: Actual rest time before this set (Optional[int]), to cover scenarios where the rest time was longer than planned, None simply means not recorded
        notes: Optional notes for this set (Optional[str])
        failure_technique: Optional failure technique used (Optional[FailureTechnique])
    """
    number: int
    weight_kg: float # include resistancy_type = "resistance band", "bodyweight", etc. in future
    rep_count: RepCount
    rpe: Optional[int] = None ## None can be used to indicate that the RPE is not yet set, or we are learning, or deload week etc.
    rep_quality_assessment: Optional[RepQualityAssessment] = None # None simply means not recorded
    actual_rest_minutes: Optional[int] = None
    notes: Optional[str] = None
    failure_technique: Optional[FailureTechnique] = None
    
    def __post_init__(self):
        """Validate working set data after initialization."""
        if self.number <= 0:
            raise TrainingLogValidationError("Set number must be positive")
        if self.weight_kg <= 0:
            raise TrainingLogValidationError("Weight must be positive")
        # rpe and rep_quality_assessment are required in schema context, but may be None when not set yet
        if self.rpe is not None:
            TrainingLogValidator.validate_rpe(self.rpe)
        if self.rep_quality_assessment is not None:
            # If a string was passed in (some callers might bypass from_dict), convert it.
            if isinstance(self.rep_quality_assessment, str):
                self.rep_quality_assessment = RepQualityAssessment.from_string(self.rep_quality_assessment)
            elif not isinstance(self.rep_quality_assessment, RepQualityAssessment):
                raise TrainingLogValidationError("rep_quality_assessment must be a RepQualityAssessment or string")
        
        if self.actual_rest_minutes is not None and self.actual_rest_minutes < 0:
            raise TrainingLogValidationError("Rest minutes cannot be negative")
        
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
            "weightKg": self.weight_kg,
            "repCount": self.rep_count.to_dict(),
            "rpe": self.rpe,
            "repQuality": (self.rep_quality_assessment.value if isinstance(self.rep_quality_assessment, RepQualityAssessment) else None),
            "actualRestMinutes": self.actual_rest_minutes,
            "notes": self.notes,
            "failureTechnique": self.failure_technique.to_dict() if self.failure_technique is not None else None,
        })
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkingSet':
        """Create WorkingSet from dictionary."""
        failure_technique = None
        if "failureTechnique" in data:
            failure_technique = FailureTechnique.from_dict(data["failureTechnique"])
        rep_count_obj = RepCount.from_dict(data.get("repCount"))
        if rep_count_obj is None:
            raise TrainingLogValidationError("WorkingSet.repCount is required")

        return cls(
            number=data["set"],
            weight_kg=data["weightKg"],
            rep_count=rep_count_obj,
            rpe=data.get("rpe"),
            rep_quality_assessment=data.get("repQuality"),
            actual_rest_minutes=data.get("actualRestMinutes"),
            notes=data.get("notes"),
            failure_technique=failure_technique
        )


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
        working_sets: List of working sets (List[WorkingSet], required)
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
    working_sets: List[WorkingSet] = field(default_factory=list)
    target_muscle_groups: Optional[List[str]] = None
    rep_tempo: Optional[str] = None
    current_goal: Optional[Goal] = None
    warmup_sets: Optional[List[WarmupSet]] = None
    notes: Optional[str] = None
    warmup_notes: Optional[str] = None
    form_cues: Optional[List[str]] = None
    
    def __post_init__(self):
        """Validate exercise data after initialization."""
        if self.number <= 0:
            raise TrainingLogValidationError("Exercise number must be positive")
        
        TrainingLogValidator.validate_string_not_empty(self.name, "exercise name")
        
        # Allow None for optional list fields; when provided, enforce the type
        if self.target_muscle_groups is not None and not isinstance(self.target_muscle_groups, list):
            raise TrainingLogValidationError("Target muscle groups must be a list if provided")
        if self.rep_tempo is not None and not self.rep_tempo.strip():
            raise TrainingLogValidationError("Rep tempo cannot be empty if provided")
        
        if self.form_cues is not None and not isinstance(self.form_cues, list):
            raise TrainingLogValidationError("Form cues must be a list if provided")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return _clean_none_and_empty({
            "Order": self.number,
            "Name": self.name,
            # Turn optional lists into None when empty so serializer can omit them
            "targetMuscleGroups": self.target_muscle_groups if self.target_muscle_groups else None,
            "warmupSets": [warmup.to_dict() for warmup in (self.warmup_sets or [])] if self.warmup_sets else None,
            "workingSets": [working.to_dict() for working in self.working_sets] if self.working_sets else None,
            "formCues": self.form_cues if self.form_cues else None,
            "repTempo": self.rep_tempo,
            "currentGoal": self.current_goal.to_dict() if self.current_goal is not None else None,
            "notes": self.notes,
            "warmupNotes": self.warmup_notes,
        })
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Exercise':
        """Create Exercise from dictionary."""
        current_goal = None
        if "currentGoal" in data:
            current_goal = Goal.from_dict(data["currentGoal"])
        
        return cls(
            number=data["Order"],
            name=data["Name"],
            target_muscle_groups=data.get("targetMuscleGroups"),
            rep_tempo=data.get("repTempo"),
            current_goal=current_goal,
            warmup_sets=[WarmupSet.from_dict(w) for w in data.get("warmupSets", [])] if "warmupSets" in data else None,
            working_sets=[WorkingSet.from_dict(w) for w in data.get("workingSets", [])],
            notes=data.get("notes"),
            warmup_notes=data.get("warmupNotes"),
            form_cues=data.get("formCues")
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
    
    def __post_init__(self):
        """Validate training session data after initialization."""
        # Validate required string fields
        for field_name in ["data_model_version", "data_model_type", "session_id", 
                          "user_id", "user_name", "date", "focus"]:
            value = getattr(self, field_name)
            TrainingLogValidator.validate_string_not_empty(value, field_name)
        
        # Validate date format
        TrainingLogValidator.validate_iso8601_date(self.date)
        
        # Validate phase and week
        TrainingLogValidator.validate_phase(self.phase)
        TrainingLogValidator.validate_week(self.week)
        
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
        return {
            "dataModelVersion": self.data_model_version,
            "dataModelType": self.data_model_type,
            "_id": self.session_id,
            "userId": self.user_id,
            "userName": self.user_name,
            "date": self.date,
            "phase": self.phase,
            "week": self.week,
            "isDeloadWeek": self.is_deload_week,
            "focus": self.focus,
            "exercises": [exercise.to_dict() for exercise in self.exercises],
            "sessionDurationMinutes": self.session_duration_minutes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TrainingSession':
        """Create TrainingSession from dictionary."""
        return cls(
            data_model_version=data["dataModelVersion"],
            data_model_type=data["dataModelType"],
            session_id=data["_id"],
            user_id=data["userId"],
            user_name=data["userName"],
            date=data["date"],
            phase=data["phase"],
            week=data["week"],
            is_deload_week=data["isDeloadWeek"],
            focus=data["focus"],
            exercises=[Exercise.from_dict(ex) for ex in data["exercises"]],
            session_duration_minutes=data["sessionDurationMinutes"]
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
    
    