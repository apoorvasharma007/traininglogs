"""Contracts for session metadata intake and mapping."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class SessionMetadataContract:
    """Canonical metadata contract used by workflow and services."""

    phase: str
    week: int
    focus: str
    is_deload: bool = False
    date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize metadata to primitive dictionary form."""
        return {
            "phase": self.phase,
            "week": self.week,
            "focus": self.focus,
            "is_deload": self.is_deload,
            "date": self.date,
        }


def default_session_metadata() -> Dict[str, Any]:
    """Default metadata values used to bootstrap intake."""
    return {
        "phase": "phase 2",
        "week": 1,
        "focus": "upper-strength",
        "is_deload": False,
    }

