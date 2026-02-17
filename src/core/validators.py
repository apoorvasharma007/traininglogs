"""
Validation layer for traininglogs.

All business rule validation happens here.
"""

from typing import Any, List, Dict, Optional


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


class Validators:
    """Business rule validators."""

    @staticmethod
    def validate_weight(weight: float) -> bool:
        """
        Validate weight value.
        
        Args:
            weight: Weight in kilograms
            
        Returns:
            True if valid
            
        Raises:
            ValidationError: If invalid
        """
        if weight < 0:
            raise ValidationError("Weight cannot be negative")
        return True

    @staticmethod
    def validate_reps(reps: int) -> bool:
        """
        Validate rep count.
        
        Args:
            reps: Number of reps
            
        Returns:
            True if valid
            
        Raises:
            ValidationError: If invalid
        """
        if reps <= 0:
            raise ValidationError("Reps must be greater than 0")
        return True

    @staticmethod
    def validate_week(week: int) -> bool:
        """
        Validate week number.
        
        Args:
            week: Week number
            
        Returns:
            True if valid
            
        Raises:
            ValidationError: If invalid
        """
        if week < 1:
            raise ValidationError("Week must be 1 or greater")
        return True

    @staticmethod
    def validate_rpe(rpe: float) -> bool:
        """
        Validate RPE (Rate of Perceived Exertion).
        
        Args:
            rpe: RPE value (typically 1-10)
            
        Returns:
            True if valid
            
        Raises:
            ValidationError: If invalid
        """
        if rpe < 1 or rpe > 10:
            raise ValidationError("RPE must be between 1 and 10")
        return True

    @staticmethod
    def validate_session(session_data: Dict[str, Any]) -> bool:
        """
        Validate complete training session.
        
        Args:
            session_data: Session dictionary
            
        Returns:
            True if valid
            
        Raises:
            ValidationError: If invalid
        """
        # Session must have at least one exercise
        exercises = session_data.get("exercises", [])
        if not exercises:
            raise ValidationError("Session must have at least 1 exercise")

        # Each exercise must have at least one working set
        for exercise in exercises:
            working_sets = exercise.get("working_sets", [])
            if not working_sets:
                raise ValidationError(
                    f"Exercise '{exercise.get('name', 'Unknown')}' must have at least 1 working set"
                )

        return True

    @staticmethod
    def validate_set_data(
        weight: Optional[float],
        full_reps: Optional[int],
        partial_reps: int = 0,
        rpe: Optional[float] = None
    ) -> bool:
        """
        Validate individual set data.
        
        Args:
            weight: Weight in kg
            full_reps: Full repetitions
            partial_reps: Partial reps (defaults to 0)
            rpe: Rate of Perceived Exertion
            
        Returns:
            True if valid
            
        Raises:
            ValidationError: If invalid
        """
        if weight is not None and weight < 0:
            raise ValidationError("Weight cannot be negative")

        if full_reps is None or full_reps <= 0:
            raise ValidationError("Full reps must be greater than 0")

        if partial_reps < 0:
            raise ValidationError("Partial reps cannot be negative")

        if rpe is not None:
            Validators.validate_rpe(rpe)

        return True
