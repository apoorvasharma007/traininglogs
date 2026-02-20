"""Contracts for parse and validation issues."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ValidationIssueContract:
    """Validation issue surfaced to conversation layer."""

    field: str
    message: str
    hint: Optional[str] = None


@dataclass(frozen=True)
class ParseIssueContract:
    """Parse issue surfaced to conversation layer."""

    raw_input: str
    message: str
    hint: Optional[str] = None

