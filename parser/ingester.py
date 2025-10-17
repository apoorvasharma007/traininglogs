# app/ingestor.py
import re
from typing import Dict, Any, List

from datamodels.models import (
    TrainingSession, Exercise, Goal, RepRange, WarmupSet, WorkingSet, RepCount,
    FailureTechnique, FailureTechniqueType, MyoRepDetails, LLPDetails, StaticDetails,
    RepQualityAssessment
)

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
        user_id = "user-123"
        user_name = "John Doe"
        session_id = f"{user_id}-{data['date']}"
        
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
            exercises=[self._create_exercise(ex_data) for ex_data in data.get('exercises', [])],
            session_duration_minutes=data['session_duration_minutes']
        )

    def _create_exercise(self, data: Dict[str, Any]) -> Exercise:
        """Creates an Exercise object from its dictionary representation."""
        goal = None
        if 'current_goal' in data:
            goal_data = data['current_goal']
            goal = Goal(
                weight_kg=goal_data['weight_kg'],
                sets=goal_data['sets'],
                rep_range=RepRange(**goal_data['rep_range']),
                rest_minutes=goal_data.get('rest_minutes', 3) # Default rest if not specified
            )

        return Exercise(
            number=data['number'],
            name=data['name'],
            current_goal=goal,
            warmup_sets=[WarmupSet(**ws) for ws in data.get('warmup_sets', [])],
            working_sets=[self._create_working_set(ws) for ws in data.get('working_sets', [])],
            notes=data.get('notes'),
            warmup_notes=data.get('warmup_notes'),
            form_cues=data.get('form_cues')
        )

    def _create_working_set(self, data: Dict[str, Any]) -> WorkingSet:
        """Creates a WorkingSet object from its dictionary representation."""
        failure_technique = None
        if 'failure_technique_raw' in data:
            failure_technique = self._parse_failure_technique(data['failure_technique_raw'])
            
        return WorkingSet(
            number=data['number'],
            weight_kg=data['weight_kg'],
            rep_count=RepCount(**data['rep_count']),
            rpe=data.get('rpe'),
            rep_quality_assessment=RepQualityAssessment.from_string(data.get('rep_quality_assessment')),
            notes=data.get('notes'),
            failure_technique=failure_technique
        )
        
    def _parse_failure_technique(self, raw_str: str) -> FailureTechnique:
        """Parses the failure technique string into the correct dataclass."""
        raw_str = raw_str.strip()
        
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