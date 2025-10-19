"""
Validation utilities for training log data.

This module provides validation functions and classes to ensure
training log data conforms to the expected schema and business rules.
"""

from typing import Any, Dict, List, Optional, Union
from .exceptions import TrainingLogValidationError


class TrainingLogValidator:
    """
    Validator class for training log data validation.
    
    Provides methods to validate individual components and complete
    training session data according to the schema requirements.
    """
    # might need at some point in future
    @staticmethod
    def validate_required_field(data: Dict[str, Any], field_name: str, field_type: type) -> None:
        """
        Validate that a required field exists and has the correct type.
        
        Args:
            data: Dictionary containing the data to validate
            field_name: Name of the field to validate
            field_type: Expected type of the field
            
        Raises:
            TrainingLogValidationError: If field is missing or has wrong type
        """
        if field_name not in data:
            raise TrainingLogValidationError(f"Required field '{field_name}' is missing")
        
        if not isinstance(data[field_name], field_type):
            raise TrainingLogValidationError(
                f"Field '{field_name}' must be of type {field_type.__name__}, "
                f"got {type(data[field_name]).__name__}"
            )
    # might need at some point in future
    @staticmethod
    def validate_optional_field(data: Dict[str, Any], field_name: str, field_type: type) -> None:
        """
        Validate that an optional field has the correct type if present.
        
        Args:
            data: Dictionary containing the data to validate
            field_name: Name of the field to validate
            field_type: Expected type of the field
            
        Raises:
            TrainingLogValidationError: If field has wrong type
        """
        if field_name in data and data[field_name] is not None:
            if not isinstance(data[field_name], field_type):
                raise TrainingLogValidationError(
                    f"Optional field '{field_name}' must be of type {field_type.__name__}, "
                    f"got {type(data[field_name]).__name__}"
                )
    
    @staticmethod
    def validate_string_not_empty(value: str, field_name: str) -> None:
        """
        Validate that a string field is not empty.
        
        Args:
            value: String value to validate
            field_name: Name of the field for error messages
            
        Raises:
            TrainingLogValidationError: If string is empty
        """
        if not isinstance(value, str):
            raise TrainingLogValidationError(f"Field '{field_name}' must be a string, got {type(value).__name__}")
        if not value or not value.strip():
            raise TrainingLogValidationError(f"Field '{field_name}' cannot be empty")
    
    @staticmethod
    def validate_positive_integer(value: int, field_name: str) -> None:
        """
        Validate that an integer field is positive.
        
        Args:
            value: Integer value to validate
            field_name: Name of the field for error messages
            
        Raises:
            TrainingLogValidationError: If integer is not positive
        """
        # Reject booleans (bool is a subclass of int)
        if isinstance(value, bool) or not isinstance(value, int):
            raise TrainingLogValidationError(f"Field '{field_name}' must be a positive integer, got {type(value).__name__}")
        if value <= 0:
            raise TrainingLogValidationError(f"Field '{field_name}' must be positive, got {value}")
    
    @staticmethod
    def validate_range(value: int, min_val: int, max_val: int, field_name: str) -> None:
        """
        Validate that an integer field is within a specified range.
        
        Args:
            value: Integer value to validate
            min_val: Minimum allowed value (inclusive)
            max_val: Maximum allowed value (inclusive)
            field_name: Name of the field for error messages
            
        Raises:
            TrainingLogValidationError: If value is outside range
        """
        # Reject booleans (bool is a subclass of int)
        if isinstance(value, bool) or not isinstance(value, int):
            raise TrainingLogValidationError(
                f"Field '{field_name}' must be an integer between {min_val} and {max_val}, got {type(value).__name__}"
            )
        if not (min_val <= value <= max_val):
            raise TrainingLogValidationError(
                f"Field '{field_name}' must be between {min_val} and {max_val}, got {value}"
            )
    
    @staticmethod
    def validate_date_string(date_string: str) -> None:
        """
        Validate that a value is a string formatted as YYYY-MM-DD (date only).

        This project uses a date-only string (no time or timezone). The method
        name is preserved for compatibility with existing callers, but the
        validator enforces the YYYY-MM-DD format and verifies the date is
        calendar-valid (e.g. rejects 2025-02-30).

        Args:
            date_string: Date value to validate

        Raises:
            TrainingLogValidationError: If not a string or not a valid YYYY-MM-DD
        """
        import re
        import datetime

        if not isinstance(date_string, str):
            raise TrainingLogValidationError(
                f"Date must be a string formatted as YYYY-MM-DD, got {type(date_string).__name__}"
            )

        pattern = r'^\d{4}-\d{2}-\d{2}$'
        if not re.match(pattern, date_string):
            raise TrainingLogValidationError(
                f"Date must be formatted as YYYY-MM-DD (e.g. 2025-10-18), got: {date_string}"
            )

        # Verify it's a real calendar date (catches invalid months/days, leap years)
        try:
            datetime.datetime.strptime(date_string, "%Y-%m-%d")
        except ValueError:
            raise TrainingLogValidationError(f"Date string is not a valid calendar date: {date_string}")

    @staticmethod
    def validate_rpe(rpe: int) -> None:
        """
        Validate that RPE is within the valid range (1-10).
        
        Args:
            rpe: RPE value to validate
            
        Raises:
            TrainingLogValidationError: If RPE is outside valid range
        """
        # RPE may be an integer (1..10) or a half-step float (e.g. 7.5).
        if isinstance(rpe, bool):
            raise TrainingLogValidationError(f"Field 'RPE' must be an integer or half-step float between 1 and 10, got {type(rpe).__name__}")

        if isinstance(rpe, int):
            TrainingLogValidator.validate_range(rpe, 1, 10, "RPE")
            return

        if isinstance(rpe, float):
            # Accept only .0 or .5 fractional parts
            if not (1.0 <= rpe <= 10.0):
                raise TrainingLogValidationError(f"Field 'RPE' must be between 1 and 10, got {rpe}")
            frac = rpe - int(rpe)
            if abs(frac - 0.0) < 1e-9 or abs(frac - 0.5) < 1e-9:
                return
            raise TrainingLogValidationError(f"Field 'RPE' must be an integer or half-step (e.g. 7 or 7.5), got {rpe}")

        raise TrainingLogValidationError(f"Field 'RPE' must be an integer or half-step float between 1 and 10, got {type(rpe).__name__}")

    
