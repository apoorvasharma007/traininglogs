# app/ingestor.py
import logging
import re
from typing import Dict, Any, List

from datamodels.models import (
    TrainingSession, Exercise, Goal, RepRange, WarmupSet, WorkingSet, RepCount,
    FailureTechnique, FailureTechniqueType, MyoRepDetails, LLPDetails, StaticDetails,
    RepQualityAssessment
)

# Module logger — don't configure root logger here so callers can control formatting/level
logger = logging.getLogger(__name__)

class DataIngestor:
    """
    Ingests a parsed dictionary and maps it to the defined dataclasses.
    """

    def ingest(self, data: Dict[str, Any]) -> TrainingSession:
        """
        Converts a dictionary from the parser into a TrainingSession object.

        Args:
            data: The structured dictionary from WorkoutParser.

        Returns:
            A populated TrainingSession dataclass object.
        """
        # A real implementation would get these from user context
        user_id = "1"
        user_name = "Apoorva Sharma"

        # Basic validation with helpful log messages
        required_top_keys = [
            'date', 'phase', 'week', 'is_deload_week', 'focus', 'session_duration_minutes'
        ]
        missing = [k for k in required_top_keys if k not in data]
        if missing:
            logger.error("Ingest failed: missing top-level keys: %s. Input keys: %s",
                         missing, list(data.keys()))
            raise KeyError(f"Missing required top-level keys for ingestion: {missing}")

        session_id = f"{user_id}-{data['date']}"
        logger.debug("Creating TrainingSession for date=%s session_id=%s", data['date'], session_id)

        try:
            # Normalize top-level date to ISO8601 if it is provided as YYYY-MM-DD
            raw_date = data.get('date')
            if isinstance(raw_date, str):
                if re.match(r"^\d{4}-\d{2}-\d{2}$", raw_date):
                    iso_date = f"{raw_date}T00:00:00Z"
                    logger.info("Normalizing date %s -> %s", raw_date, iso_date)
                    data['date'] = iso_date
                    session_id = f"{user_id}-{data['date']}"
                else:
                    # leave as-is (may already be ISO)
                    pass
            exercises_raw = data.get('exercises', [])
            if not isinstance(exercises_raw, list):
                logger.error("Expected 'exercises' to be a list but got %s", type(exercises_raw))
                raise TypeError("'exercises' must be a list")

            exercises = [self._create_exercise(ex_data) for ex_data in exercises_raw]

            return TrainingSession(
                data_model_version="1.0",
                data_model_type="TrainingLog",
                session_id=session_id,
                user_id=user_id,
                user_name=user_name,
                date=data['date'],
                phase=data['phase'],
                week=data['week'],
                is_deload_week=data['is_deload_week'],
                focus=data['focus'],
                exercises=exercises,
                session_duration_minutes=data['session_duration_minutes']
            )
        except Exception as exc:
            # Log context and re-raise so callers can decide how to handle it
            logger.exception("Failed to build TrainingSession from parsed data. data keys: %s", list(data.keys()))
            raise

    def _create_exercise(self, data: Dict[str, Any]) -> Exercise:
        """Creates an Exercise object from its dictionary representation."""
        logger.debug("Creating Exercise from data keys: %s", list(data.keys()))
        goal = None
        try:
            if 'current_goal' in data and data['current_goal'] is not None:
                goal_data = data['current_goal']
                logger.debug("Parsing current_goal for exercise %s: %s", data.get('name'), goal_data)
                goal = Goal(
                    weight_kg=goal_data['weight_kg'],
                    sets=goal_data['sets'],
                    rep_range=RepRange(**goal_data['rep_range']),
                    rest_minutes=goal_data.get('rest_minutes', 3) # Default rest if not specified
                )

            # Validate exercise identity
            if 'number' not in data or 'name' not in data:
                logger.error("Exercise entry missing 'number' or 'name'. Entry: %s", data)
                raise KeyError("Exercise must include 'number' and 'name'")

            # Warmup sets
            warmup_raw = data.get('warmup_sets', [])
            if warmup_raw is None:
                warmup_raw = []
            if not isinstance(warmup_raw, list):
                logger.error("Exercise.warmup_sets is not a list for exercise %s", data.get('name'))
                raise TypeError("warmup_sets must be a list")
            warmup_sets = []
            for i, ws in enumerate(warmup_raw):
                try:
                    warmup_sets.append(WarmupSet(**ws))
                except Exception:
                    logger.exception("Failed to parse warmup set #%s for exercise %s. set data: %s", i + 1, data.get('name'), ws)
                    raise

            # Working sets
            working_raw = data.get('working_sets', [])
            if working_raw is None:
                working_raw = []
            if not isinstance(working_raw, list):
                logger.error("Exercise.working_sets is not a list for exercise %s", data.get('name'))
                raise TypeError("working_sets must be a list")
            working_sets = []
            for ws in working_raw:
                try:
                    working_sets.append(self._create_working_set(ws))
                except Exception:
                    logger.exception("Failed to parse working set for exercise %s. set data: %s", data.get('name'), ws)
                    raise

            return Exercise(
                number=data['number'],
                name=data['name'],
                current_goal=goal,
                warmup_sets=warmup_sets,
                working_sets=working_sets,
                notes=data.get('notes'),
                warmup_notes=data.get('warmup_notes'),
                form_cues=data.get('form_cues')
            )
        except Exception:
            logger.exception("Error while creating Exercise object from data: %s", data)
            raise

    def _create_working_set(self, data: Dict[str, Any]) -> WorkingSet:
        """Creates a WorkingSet object from its dictionary representation."""
        logger.debug("Creating WorkingSet from data keys: %s", list(data.keys()))
        failure_technique = None
        try:
            if 'failure_technique_raw' in data and data['failure_technique_raw'] is not None:
                try:
                    failure_technique = self._parse_failure_technique(data['failure_technique_raw'])
                except Exception:
                    logger.exception("Failed to parse failure technique for working set: %s", data.get('failure_technique_raw'))
                    raise

            # rep_count should be a dict with at least 'full'
            if 'rep_count' not in data or data['rep_count'] is None:
                logger.error("Working set missing 'rep_count'. Working set data: %s", data)
                raise KeyError("Working set missing 'rep_count'")

            try:
                rep_count_obj = RepCount(**data['rep_count'])
            except Exception:
                logger.exception("Failed to construct RepCount from: %s", data.get('rep_count'))
                raise

            rep_quality = None
            try:
                rep_quality = RepQualityAssessment.from_string(data.get('rep_quality_assessment'))
            except Exception:
                logger.exception("Invalid rep_quality_assessment value: %s", data.get('rep_quality_assessment'))
                raise

            # Normalize RPE to float always (e.g. 7 -> 7.0). Validators accept half-steps.
            raw_rpe = data.get('rpe')
            normalized_rpe = None
            if raw_rpe is not None:
                try:
                    normalized_rpe = float(raw_rpe)
                except Exception:
                    logger.exception("Invalid RPE value type for working set: %s", raw_rpe)
                    raise

            return WorkingSet(
                number=data['number'],
                weight_kg=data['weight_kg'],
                rep_count=rep_count_obj,
                rpe=normalized_rpe,
                rep_quality_assessment=rep_quality,
                notes=data.get('notes'),
                failure_technique=failure_technique
            )
        except Exception:
            logger.exception("Error while creating WorkingSet from data: %s", data)
            raise
        
    def _parse_failure_technique(self, raw_str: str) -> FailureTechnique:
        """Parses the failure technique string into the correct dataclass."""
        raw_str = raw_str.strip()
        logger.debug("Parsing failure technique from raw string: %s", raw_str)
        
        # MyoReps: e.g., myo(3,3,2+1)
        myo_match = re.match(r"myo\((.*)\)", raw_str, re.IGNORECASE)
        if myo_match:
            mini_sets_str = myo_match.group(1).split(',')
            mini_sets = []
            for i, rep_str in enumerate(mini_sets_str):
                full_reps, partial_reps = (0, 0)
                if '+' in rep_str:
                    full_reps, partial_reps = map(int, rep_str.split('+'))
                else:
                    full_reps = int(rep_str)
                
                mini_sets.append({
                    "miniSet": i + 1,
                    "repCount": RepCount(full=full_reps, partial=partial_reps)
                })
            details = MyoRepDetails(mini_sets=mini_sets)
            return FailureTechnique(technique_type=FailureTechniqueType.MYO_REPS, details=details)
        
        # LLP: e.g., llp(6)
        llp_match = re.match(r"llp\((\d+)\)", raw_str, re.IGNORECASE)
        if llp_match:
            details = LLPDetails(partial_rep_count=int(llp_match.group(1)))
            return FailureTechnique(technique_type=FailureTechniqueType.LLP, details=details)
            
        # Static Hold: e.g., static(30 sec)
        static_match = re.match(r"static\((\d+)\s*sec\)", raw_str, re.IGNORECASE)
        if static_match:
            details = StaticDetails(hold_duration_seconds=int(static_match.group(1)))
            return FailureTechnique(technique_type=FailureTechniqueType.STATIC, details=details)

        raise ValueError(f"Unknown failure technique format: {raw_str}")