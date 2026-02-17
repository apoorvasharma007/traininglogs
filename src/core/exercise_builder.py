"""
Interactive exercise builder for traininglogs CLI.

Handles user prompts for building exercises with warmup and working sets.
"""

from typing import Dict, Any, Optional, List
from core.validators import Validators, ValidationError


class ExerciseBuilder:
    """Interactive builder for exercises."""

    def __init__(self):
        """Initialize ExerciseBuilder."""
        self.validators = Validators()

    def build_exercise(
        self,
        exercise_name: str,
        last_exercise_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Interactively build an exercise with sets.
        
        Args:
            exercise_name: Name of the exercise
            last_exercise_data: Optional previous exercise data for reference
            
        Returns:
            Complete exercise dictionary
        """
        exercise = {
            "name": exercise_name,
            "warmup_sets": [],
            "working_sets": []
        }

        # Show previous exercise info if available
        if last_exercise_data:
            self._show_last_exercise(last_exercise_data)

        # Build warmup sets
        print(f"\n📝 Building warmup sets for: {exercise_name}")
        exercise["warmup_sets"] = self._build_sets("warmup")

        # Build working sets
        print(f"\n📝 Building working sets for: {exercise_name}")
        exercise["working_sets"] = self._build_sets("working")

        return exercise

    def _build_sets(self, set_type: str) -> List[Dict[str, Any]]:
        """
        Interactively build sets of given type.
        
        Args:
            set_type: "warmup" or "working"
            
        Returns:
            List of set dictionaries
        """
        sets = []
        set_number = 1

        while True:
            print(f"\n  {set_type.capitalize()} Set #{set_number}")
            
            try:
                set_data = self._build_single_set(set_type, set_number)
                sets.append(set_data)
                
                # Ask if user wants to add another set
                another = input(f"\n  Add another {set_type} set? (y/n): ").strip().lower()
                if another != 'y':
                    break
                
                set_number += 1
            except ValidationError as e:
                print(f"  ❌ Error: {e}")
                print(f"  Please try again.")
                continue
            except KeyboardInterrupt:
                print(" (cancelled)")
                break

        return sets

    def _build_single_set(self, set_type: str, set_number: int) -> Dict[str, Any]:
        """
        Build a single set with user prompts.
        
        Args:
            set_type: "warmup" or "working"
            set_number: Set number for display
            
        Returns:
            Set dictionary
        """
        set_data = {}

        # Get weight
        while True:
            try:
                weight_input = input(f"    Weight (kg): ").strip()
                if weight_input == "":
                    weight = 0  # Allow empty for bodyweight
                else:
                    weight = float(weight_input)
                self.validators.validate_weight(weight)
                set_data["weight_kg"] = weight
                break
            except (ValueError, ValidationError) as e:
                print(f"    ❌ Invalid weight: {e}")

        # Get full reps
        while True:
            try:
                full_reps = int(input(f"    Full reps: ").strip())
                self.validators.validate_reps(full_reps)
                set_data["full_reps"] = full_reps
                break
            except (ValueError, ValidationError) as e:
                print(f"    ❌ Invalid reps: {e}")

        # Get partial reps (optional, only for working sets)
        if set_type == "working":
            try:
                partial_input = input(f"    Partial reps (or press Enter for 0): ").strip()
                partial_reps = int(partial_input) if partial_input else 0
                if partial_reps < 0:
                    raise ValidationError("Partial reps cannot be negative")
                set_data["partial_reps"] = partial_reps
            except ValueError:
                print("    ❌ Invalid partial reps, defaulting to 0")
                set_data["partial_reps"] = 0

            # Get RPE (optional)
            while True:
                try:
                    rpe_input = input(f"    RPE (1-10, or press Enter to skip): ").strip()
                    if rpe_input == "":
                        break
                    rpe = float(rpe_input)
                    self.validators.validate_rpe(rpe)
                    set_data["rpe"] = rpe
                    break
                except (ValueError, ValidationError) as e:
                    print(f"    ❌ Invalid RPE: {e}")

            # Get rep quality assessment (optional)
            quality_input = input(f"    Rep quality (good/bad/perfect/learning, or skip): ").strip().lower()
            if quality_input in ["good", "bad", "perfect", "learning"]:
                set_data["rep_quality"] = quality_input

        return set_data

    def _show_last_exercise(self, last_exercise: Dict[str, Any]):
        """
        Display previous exercise data for reference.
        
        Args:
            last_exercise: Previous exercise data
        """
        print("\n📚 Last occurrence of this exercise:")
        
        # Show last working set
        working_sets = last_exercise.get("working_sets", [])
        if working_sets:
            last_set = working_sets[-1]
            weight = last_set.get("weight_kg", "N/A")
            full_reps = last_set.get("full_reps", "N/A")
            partial_reps = last_set.get("partial_reps", 0)
            rpe = last_set.get("rpe", "N/A")
            
            print(f"   Last working set: {weight}kg × {full_reps} + {partial_reps}p @ RPE {rpe}")
