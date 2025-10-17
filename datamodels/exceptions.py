"""
Custom exceptions for the training logs package.

This module defines custom exception classes for handling validation errors
and other specific issues that may occur when working with training log data.
"""


class TrainingLogValidationError(Exception):
    """
    Raised when validation of training log data fails.
    
    This exception is raised when any validation rule is violated,
    such as invalid data types, missing required fields, or values
    outside acceptable ranges.
    """
    pass


class TrainingLogDataError(Exception):
    """
    Raised when there are issues with the structure or format of training log data.
    
    This exception is raised when the data structure doesn't match
    the expected schema or when there are inconsistencies in the data.
    """
    pass


class TrainingLogVersionError(Exception):
    """
    Raised when there are version compatibility issues with training log data.
    
    This exception is raised when the data model version is not supported
    or when there are breaking changes in the schema.
    """
    pass
