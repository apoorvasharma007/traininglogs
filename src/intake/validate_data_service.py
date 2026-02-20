"""Service for strict validation and normalization of intake payloads."""

import re
from typing import Any, Dict

from core.validators import ValidationError, Validators


class ValidateDataService:
    """Validate metadata, set payloads, and draft exercise structures."""

    def validate_metadata(self, metadata: Dict[str, Any]) -> bool:
        phase = str(metadata.get("phase", "")).strip().lower()
        week = metadata.get("week")
        focus = str(metadata.get("focus", "")).strip().lower()
        is_deload = metadata.get("is_deload")

        if not re.fullmatch(r"phase\s+[1-9][0-9]*", phase):
            raise ValidationError("Phase must look like: phase 1, phase 2, ...")

        try:
            Validators.validate_week(int(week))
        except (TypeError, ValueError):
            raise ValidationError("Week must be an integer >= 1")

        if not focus:
            raise ValidationError("Focus is required")

        if not isinstance(is_deload, bool):
            raise ValidationError("Deload must be true/false")

        return True

    def normalize_and_validate_set_data(
        self,
        set_data: Dict[str, Any],
        is_warmup: bool,
    ) -> Dict[str, Any]:
        """Normalize numeric fields and validate one set."""
        if set_data is None:
            raise ValidationError("Set data is required")

        try:
            weight = float(set_data.get("weight"))
            reps = int(set_data.get("reps"))
        except (TypeError, ValueError):
            raise ValidationError("Set requires numeric weight and integer reps")

        rpe_raw = set_data.get("rpe")
        rpe = float(rpe_raw) if rpe_raw is not None else None

        Validators.validate_weight(weight)
        Validators.validate_reps(reps)
        if rpe is not None:
            Validators.validate_rpe(rpe)

        if is_warmup and reps > 20:
            raise ValidationError("Warmup reps should be <= 20")
        if not is_warmup and reps > 50:
            raise ValidationError("Working reps should be <= 50")

        normalized = {"weight": weight, "reps": reps}
        if rpe is not None:
            normalized["rpe"] = rpe
        return normalized

    def validate_exercise_name(self, exercise_name: str) -> bool:
        name = (exercise_name or "").strip()
        if len(name) < 2:
            raise ValidationError("Exercise name must be at least 2 characters")
        return True

    def validate_draft_for_commit(self, draft: Dict[str, Any]) -> bool:
        if not draft:
            raise ValidationError("No active draft to commit")
        self.validate_exercise_name(draft.get("name", ""))
        working_sets = draft.get("working_sets", [])
        if not working_sets:
            raise ValidationError("Draft must include at least one working set")
        return True

