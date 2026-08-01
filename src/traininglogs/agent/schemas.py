from __future__ import annotations

import datetime
import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from traininglogs.models.models import Exercise, SessionCooldown, SessionWarmup


class TrainingLogLLMExtract(BaseModel):
    date: str
    program: Optional[str] = None
    phase: Optional[int] = None
    week: Optional[int] = None
    is_deload_week: Optional[bool] = None
    focus: Optional[str] = None
    session_duration_minutes: Optional[int] = None
    warmup: Optional[List[SessionWarmup]] = None
    exercises: List[Exercise]
    cooldown: Optional[List[SessionCooldown]] = None
    notes: Optional[str] = None
    uncertain_fields: List[str] = Field(default_factory=list)

    @field_validator("date")
    @classmethod
    def valid_date(cls, v: str) -> str:
        if not isinstance(v, str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("Date must be formatted as YYYY-MM-DD")
        try:
            datetime.datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Date is not a valid calendar date: {v}")
        return v


class LLMParserError(Exception):
    pass
