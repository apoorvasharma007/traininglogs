"""Contracts for persistence outcomes and session-level status."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PersistenceOutcomeContract:
    """Write result for local DB + cloud DB + JSON export flow."""

    saved_local: bool
    saved_json: bool
    saved_cloud: bool
    status: str
    local_error: Optional[str] = None
    json_error: Optional[str] = None
    cloud_error: Optional[str] = None
    cloud_mode: str = "disabled"

