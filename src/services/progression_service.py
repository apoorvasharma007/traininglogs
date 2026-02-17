"""
Progression service - suggests next weight/reps based on history.

Intelligent suggestions for progression without UI coupling.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from services.history_service import HistoryService


@dataclass
class ProgressionSuggestion:
    """Suggested next weight and reps."""
    suggested_weight: float
    reasoning: str
    confidence: float  # 0-1
    alternatives: List[float]


class ProgressionService:
    """Suggest intelligent progression based on history."""

    def __init__(self, history_service: HistoryService):
        """
        Initialize progression service.
        
        Args:
            history_service: HistoryService for accessing history
        """
        self.history = history_service

    def suggest_next_weight(
        self,
        exercise_name: str,
        current_weight: float,
        current_reps: int,
        current_rpe: Optional[float] = None
    ) -> ProgressionSuggestion:
        """
        Suggest next weight based on history and current performance.
        
        Logic:
        - If current weight matches last weight AND reps increased: increase weight
        - If current weight matches last weight AND RPE < 8: increase weight
        - If current weight < max achieved: encourage to reach max
        - Otherwise: small incremental increase (2.5kg for upper, 5kg for lower)
        
        Args:
            exercise_name: Name of exercise
            current_weight: Weight just attempted
            current_reps: Reps achieved
            current_rpe: RPE of attempt (optional)
            
        Returns:
            ProgressionSuggestion with weight recommendation
        """
        last = self.history.get_last_exercise(exercise_name)
        max_weight = self.history.get_max_weight_achieved(exercise_name)

        # Scenario 1: New exercise
        if not last:
            return ProgressionSuggestion(
                suggested_weight=current_weight,
                reasoning="New exercise - start here and build",
                confidence=0.8,
                alternatives=[current_weight - 2.5, current_weight + 2.5]
            )

        last_weight = last.get_max_weight() or 0
        last_reps = max(
            (s.get("reps", 0) for s in last.working_sets),
            default=0
        )

        # Scenario 2: Reps increased at same weight
        if current_weight == last_weight and current_reps > last_reps:
            increment = self._get_increment(exercise_name)
            return ProgressionSuggestion(
                suggested_weight=round(current_weight + increment, 1),
                reasoning=f"Reps increased from {last_reps} to {current_reps} - try +{increment}kg",
                confidence=0.9,
                alternatives=[
                    round(current_weight + increment/2, 1),
                    round(current_weight + increment * 1.5, 1)
                ]
            )

        # Scenario 3: Good RPE at same weight
        if current_weight == last_weight and (current_rpe or 7) < 8:
            increment = self._get_increment(exercise_name)
            return ProgressionSuggestion(
                suggested_weight=round(current_weight + increment, 1),
                reasoning=f"RPE {current_rpe or 7}/10 suggests room to increase",
                confidence=0.85,
                alternatives=[
                    round(current_weight + increment/2, 1),
                    round(current_weight + increment * 1.5, 1)
                ]
            )

        # Scenario 4: Below max weight achieved
        if max_weight and current_weight < max_weight:
            return ProgressionSuggestion(
                suggested_weight=min(max_weight, round(current_weight + 2.5, 1)),
                reasoning=f"You've lifted {max_weight}kg before - challenge yourself",
                confidence=0.7,
                alternatives=[current_weight, round(current_weight + 2.5, 1)]
            )

        # Scenario 5: Normal progression
        increment = self._get_increment(exercise_name)
        return ProgressionSuggestion(
            suggested_weight=round(current_weight + increment, 1),
            reasoning=f"Standard progression: +{increment}kg",
            confidence=0.8,
            alternatives=[
                round(current_weight + increment/2, 1),
                current_weight  # Stay same
            ]
        )

    def suggest_rep_range(
        self,
        exercise_name: str
    ) -> Optional[Tuple[int, int]]:
        """
        Suggest reasonable rep range based on history.
        
        Args:
            exercise_name: Name of exercise
            
        Returns:
            (min_reps, max_reps) tuple or None
        """
        rpe_range = self.history.get_typical_rpe_range(exercise_name, min_samples=2)
        
        if not rpe_range:
            # Default ranges by typical rep targets
            return (6, 10)  # Fairly standard

        # Higher RPE typically at lower reps
        avg_rpe = rpe_range[1]
        if avg_rpe >= 8.5:
            return (3, 6)
        elif avg_rpe >= 7.5:
            return (6, 10)
        else:
            return (8, 12)

    def suggest_warmups(
        self,
        exercise_name: str,
        target_weight: float
    ) -> List[Dict[str, float]]:
        """
        Suggest good warmup progression to target weight.
        
        Args:
            exercise_name: Name of exercise
            target_weight: Target working weight
            
        Returns:
            List of sets [{'weight': X, 'reps': Y}, ...]
        """
        # Smart warmup: 50%, 75%, 90% of target
        setups = []

        w1 = round(target_weight * 0.5, 1)
        setups.append({'weight': w1, 'reps': 5})

        w2 = round(target_weight * 0.75, 1)
        if w2 > w1:
            setups.append({'weight': w2, 'reps': 3})

        w3 = round(target_weight * 0.9, 1)
        if w3 > w2:
            setups.append({'weight': w3, 'reps': 2})

        return setups

    def get_volume_trend(
        self,
        exercise_name: str,
        weeks: int = 4
    ) -> Optional[Dict[str, float]]:
        """
        Analyze volume trend over recent weeks.
        
        Args:
            exercise_name: Name of exercise
            weeks: Number of weeks to analyze
            
        Returns:
            Dict with trend data or None
        """
        history = self.history.get_exercise_progression(exercise_name, limit=20)
        if not history:
            return None

        total_volume = 0
        set_count = 0

        for occurrence in history:
            for set_data in occurrence.working_sets:
                weight = set_data.get("weight", 0)
                reps = set_data.get("reps", 0)
                total_volume += weight * reps
                set_count += 1

        avg_volume_per_set = total_volume / set_count if set_count > 0 else 0

        return {
            "total_volume": total_volume,
            "avg_volume_per_set": avg_volume_per_set,
            "set_count": set_count,
            "trend": "increasing" if len(history) > 2 else "neutral"
        }

    # Private helpers

    def _get_increment(self, exercise_name: str) -> float:
        """
        Get recommended weight increment.
        
        Heuristic: Upper body +2.5kg, lower body +5kg
        """
        lower_exercises = [
            "squat", "deadlift", "leg press",
            "leg curl", "leg extension", "hack squat"
        ]
        
        is_lower = any(
            word in exercise_name.lower() 
            for word in lower_exercises
        )
        
        return 5.0 if is_lower else 2.5
