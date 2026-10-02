"""Edits made directly on the card, turned into extract edits without an LLM.

The card and the extract name some things differently -- the card shows `reps: "8+1"`, the
extract stores `rep_count: {full: 8, partial: 1}` -- and the person only ever sees the card.
This module is the one place that knows how a card value maps onto the extract, so the UI never
has to. Each card element already carries its own `path` (ValidationCardBuilder); an edit
names that path, the card field, and the new value.

What can be edited is an allowlist, `EDITABLE_FIELDS`. Making another field editable is one
entry there. Range checks (RPE, negative weight, ...) are not repeated here: every edit is
applied with `apply_edits` and the whole extract is re-validated, so the model validators stay
the single source of those rules.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from traininglogs.agent.patch import FieldEdit, PatchError, apply_edits
from traininglogs.agent.reps import parse_reps
from traininglogs.agent.schemas import TrainingLogLLMExtract

# Card field name -> extract field name, per kind of card element. `reps` on a working set is
# not here: it is text that becomes two extract fields, handled by _reps_edits.
EDITABLE_FIELDS: dict[str, dict[str, str]] = {
    "session": {
        "date": "date",
        "focus": "focus",
        "program": "program",
        "phase": "phase",
        "week": "week",
        "is_deload_week": "is_deload_week",
        "duration_minutes": "session_duration_minutes",
        "notes": "notes",
    },
    "exercise": {
        "name": "name",
        "notes": "notes",
        "warmup_notes": "warmup_notes",
    },
    "set": {
        "weight_kg": "weight_kg",
        "rpe": "rpe",
        "quality": "rep_quality_assessment",
        "duration_seconds": "duration_seconds",
        "distance_meters": "distance_meters",
        "heart_rate_bpm": "heart_rate_bpm",
        "notes": "notes",
    },
    "warmup_set": {
        "weight_kg": "weight_kg",
        "rep_count": "rep_count",
        "notes": "notes",
    },
    "movement": {
        "name": "name",
        "reps": "reps",
        "duration_seconds": "duration_seconds",
        "notes": "notes",
    },
}

_REPS_FIELDS = ("rep_count", "unilateral_rep_count")


class CardEdit(BaseModel):
    """One value changed on the card: the element's `path`, the card field, the new value."""

    path: str
    field: str
    value: Any = None


class CardEditError(Exception):
    """An edit that can't be applied. The message names the field, for showing to the person."""


def element_kind(path: str) -> str:
    """Which kind of card element a path points at, from its shape alone."""
    steps = path.split(".") if path else []
    shape = [s if not s.isdigit() else "#" for s in steps]
    kinds = {
        (): "session",
        ("exercises", "#"): "exercise",
        ("exercises", "#", "sets", "#"): "set",
        ("exercises", "#", "warmup_sets", "#"): "warmup_set",
        ("warmup", "#"): "movement",
        ("cooldown", "#"): "movement",
    }
    kind = kinds.get(tuple(shape))
    if kind is None:
        raise CardEditError(f"{path!r} is not a card element that can be edited")
    return kind


def _join(path: str, field: str) -> str:
    return f"{path}.{field}" if path else field


def _reps_edits(path: str, value: Any) -> list[FieldEdit]:
    text = None if value is None else str(value)
    parsed = parse_reps(text)
    if text and text.strip() and parsed.rep_count is None and parsed.unilateral is None:
        raise CardEditError(
            f"{_join(path, 'reps')}: couldn't read reps from {text!r} -- "
            "write it like 8, 8+1, or L8/R7"
        )
    return [
        FieldEdit(path=_join(path, "rep_count"), value=_dump(parsed.rep_count)),
        FieldEdit(path=_join(path, "unilateral_rep_count"), value=_dump(parsed.unilateral)),
    ]


def _dump(model: BaseModel | None) -> dict | None:
    return model.model_dump(mode="json") if model is not None else None


def to_field_edits(edit: CardEdit) -> list[FieldEdit]:
    """The extract edits one card edit stands for. An empty string means "clear it"."""
    kind = element_kind(edit.path)
    value = None if edit.value == "" else edit.value

    if kind == "set" and edit.field == "reps":
        return _reps_edits(edit.path, value)

    extract_field = EDITABLE_FIELDS[kind].get(edit.field)
    if extract_field is None:
        raise CardEditError(f"{_join(edit.path, edit.field)}: this field can't be edited here")
    return [FieldEdit(path=_join(edit.path, extract_field), value=value)]


def _validation_message(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in exc.errors()
    )


def apply_card_edits(
    extract: TrainingLogLLMExtract, edits: list[CardEdit]
) -> tuple[TrainingLogLLMExtract, list[FieldEdit]]:
    """Apply card edits to `extract` and return the result plus the extract edits made.

    Fields the person edited are dropped from `uncertain_fields` -- they have now looked at
    them. Raises CardEditError, with a message naming the field, if any edit can't be applied
    or leaves the extract invalid; nothing is applied in that case.
    """
    field_edits = [fe for edit in edits for fe in to_field_edits(edit)]

    try:
        patched = apply_edits(extract.model_dump(mode="json"), field_edits)
    except PatchError as exc:
        raise CardEditError(str(exc)) from exc

    edited_paths = {fe.path for fe in field_edits} | {_join(e.path, e.field) for e in edits}
    patched["uncertain_fields"] = [
        p
        for p in patched["uncertain_fields"]
        if not any(p == e or p.startswith(e + ".") for e in edited_paths)
    ]

    try:
        return TrainingLogLLMExtract.model_validate(patched), field_edits
    except ValidationError as exc:
        raise CardEditError(_validation_message(exc)) from exc
