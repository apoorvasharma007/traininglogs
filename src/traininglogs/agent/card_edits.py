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

from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from traininglogs.agent.patch import FieldEdit, PatchError, apply_edits
from traininglogs.agent.reps import parse_reps
from traininglogs.agent.schemas import TrainingLogLLMExtract
from traininglogs.models.models import Exercise, WarmupSet, WorkingSet

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


class CardOp(BaseModel):
    """A structural change: add or remove a line. `path` is the line it applies to --
    see apply_card_op for what each op accepts."""

    op: Literal["add_set", "add_warmup_set", "add_exercise", "remove"]
    path: str


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


# ---- adding and removing lines ----

NEW_EXERCISE_NAME = "New exercise"


def _new_set(neighbour: dict | None) -> dict:
    # Weight and reps carry over from the neighbour -- the usual case is "same again". RPE,
    # quality, notes and failure technique don't: they describe how that one set went, and a
    # copied failure technique would be invalid without RPE 10 anyway.
    carried = {k: neighbour[k] for k in ("weight_kg", "rep_count", "unilateral_rep_count")} \
        if neighbour else {}
    return WorkingSet.model_validate({"number": 1, **carried}).model_dump(mode="json")


def _new_warmup_set(neighbour: dict | None) -> dict:
    # WarmupSet requires a weight; with nothing to copy, 0 (bodyweight) until edited.
    weight = neighbour["weight_kg"] if neighbour else 0.0
    rep_count = neighbour["rep_count"] if neighbour else None
    return WarmupSet(number=1, weight_kg=weight, rep_count=rep_count).model_dump(mode="json")


def _new_exercise(_: dict | None) -> dict:
    return Exercise(number=1, name=NEW_EXERCISE_NAME).model_dump(mode="json")


# op -> (kind of line it creates, the list key under an exercise, factory)
_ADDS = {
    "add_set": ("set", "sets", _new_set),
    "add_warmup_set": ("warmup_set", "warmup_sets", _new_warmup_set),
    "add_exercise": ("exercise", None, _new_exercise),
}
_REMOVABLE = {"set", "warmup_set", "exercise", "movement"}


def _split(path: str) -> tuple[str, int]:
    """'exercises.0.sets.2' -> ('exercises.0.sets', 2)."""
    list_path, _, index = path.rpartition(".")
    return list_path, int(index)


def _existing(path: str, items_of: Any) -> tuple[str, int]:
    """_split, for a path that must name a line that exists."""
    list_path, index = _split(path)
    count = len(items_of(list_path))
    if index >= count:
        raise CardEditError(f"{path}: position {index} is out of range, there are {count} items")
    return list_path, index


def _get(data: dict, path: str) -> Any:
    target: Any = data
    for step in path.split("."):
        target = target[int(step)] if isinstance(target, list) else target[step]
    return target


def _target(op: CardOp, kind: str, items_of: Any) -> tuple[str, int]:
    """Which list an add goes into, and at what position."""
    child_kind, child_key, _ = _ADDS[op.op]
    if op.op == "add_exercise":
        if kind == "session":
            return "exercises", len(items_of("exercises"))
        if kind == "exercise":
            list_path, index = _existing(op.path, items_of)
            return list_path, index + 1
    else:
        if kind == "exercise":
            list_path = f"{op.path}.{child_key}"
            return list_path, len(items_of(list_path))
        if kind == child_kind:
            list_path, index = _existing(op.path, items_of)
            return list_path, index + 1
    raise CardEditError(f"{op.op} can't be applied to {op.path!r}")


def _reindex(paths: list[str], list_path: str, moved: dict[int, int]) -> list[str]:
    """Shift position-keyed paths under `list_path` by `moved` (old -> new position);
    paths under a position missing from `moved` belonged to a removed line and are dropped."""
    prefix = list_path + "."
    result = []
    for p in paths:
        if not p.startswith(prefix):
            result.append(p)
            continue
        head, dot, tail = p[len(prefix):].partition(".")
        if not head.isdigit():
            result.append(p)
        elif int(head) in moved:
            result.append(f"{prefix}{moved[int(head)]}{dot}{tail}")
    return result


def apply_card_op(
    extract: TrainingLogLLMExtract, op: CardOp
) -> tuple[TrainingLogLLMExtract, list[FieldEdit], str | None]:
    """Add or remove one line. Returns the new extract, the extract edit made (the whole new
    list, as one list-level FieldEdit), and the path of the created line (None for remove).

    `add_set` / `add_warmup_set`: on an exercise, appends; on a set of that kind, inserts right
    after it. `add_exercise`: on `""`, appends; on an exercise, inserts after it. `remove`: any
    set, warmup set, exercise, or warmup/cooldown movement. The changed list is renumbered
    1..n, and `uncertain_fields` shifts with the positions.
    """
    data = extract.model_dump(mode="json")
    kind = element_kind(op.path)

    def items_of(path: str) -> list[dict]:
        try:
            return _get(data, path) or []
        except (IndexError, KeyError) as exc:
            raise CardEditError(f"{path}: no such line") from exc

    if op.op == "remove":
        if kind not in _REMOVABLE:
            raise CardEditError(f"{op.path!r} can't be removed")
        list_path, index = _existing(op.path, items_of)
        items = items_of(list_path)
        new_items = items[:index] + items[index + 1:]
        moved = {i: i if i < index else i - 1 for i in range(len(items)) if i != index}
        created_path = None
    else:
        list_path, index = _target(op, kind, items_of)
        items = items_of(list_path)
        neighbour = items[index - 1] if index > 0 else (items[0] if items else None)
        new_items = items[:index] + [_ADDS[op.op][2](neighbour)] + items[index:]
        moved = {i: i if i < index else i + 1 for i in range(len(items))}
        created_path = f"{list_path}.{index}"

    new_items = [{**item, "number": n} for n, item in enumerate(new_items, start=1)]
    field_edits = [FieldEdit(path=list_path, value=new_items)]

    try:
        patched = apply_edits(data, field_edits)
    except PatchError as exc:
        raise CardEditError(str(exc)) from exc
    patched["uncertain_fields"] = _reindex(patched["uncertain_fields"], list_path, moved)

    try:
        return TrainingLogLLMExtract.model_validate(patched), field_edits, created_path
    except ValidationError as exc:
        raise CardEditError(_validation_message(exc)) from exc
