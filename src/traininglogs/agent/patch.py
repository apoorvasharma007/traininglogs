"""Corrections as edits, not as a rewritten document.

The correction path used to send the whole extract and ask for the whole extract back, with
"keep all unchanged fields exactly as they are" in the prompt as the only guarantee. That is a
hope, not a mechanism: nothing stopped the model from quietly altering a set it was not asked
about, and nothing would have detected it. It also ran on the monolithic prompt at
max_tokens=4096, the ceiling that truncated 2 of 6 files in the evaluation — so a long session
could be corrected into a shorter one.

A patch inverts both problems. The model names the fields it is changing and nothing else, so
fields it does not name **cannot** change — that is a property of the code, not of the prompt.
And the output is a handful of edits rather than a whole document, so length stops mattering.
"""
from __future__ import annotations

import copy
from typing import Any, List

from pydantic import BaseModel, Field, field_validator


class FieldEdit(BaseModel):
    """One field to change, addressed by dot-path."""

    path: str = Field(
        description=(
            "Dot-path to the field, e.g. 'exercises.2.sets.0.rpe' or "
            "'exercises.1.name'. List positions are zero-based numbers. The path must "
            "already exist in the extract."
        )
    )
    value: Any = Field(
        description=(
            "The new value for that field. Use null to clear it. To add or remove items from "
            "a list, give the path of the whole list and the complete new list as the value."
        )
    )

    @field_validator("path")
    @classmethod
    def path_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Edit path cannot be empty")
        return v


class ExtractPatch(BaseModel):
    """Every change the correction asks for, and nothing else."""

    edits: List[FieldEdit] = Field(
        description="One entry per field being changed. Empty if the correction changes nothing."
    )


class PatchError(Exception):
    """A patch that cannot be applied to this extract."""


def _resolve_step(container: Any, step: str, path: str) -> Any:
    if isinstance(container, list):
        if not step.lstrip("-").isdigit():
            raise PatchError(f"{path}: '{step}' is not a list position")
        index = int(step)
        if not -len(container) <= index < len(container):
            raise PatchError(
                f"{path}: position {index} is out of range, there are {len(container)} items"
            )
        return container[index]
    if isinstance(container, dict):
        if step not in container:
            raise PatchError(f"{path}: '{step}' is not a field here")
        return container[step]
    raise PatchError(f"{path}: '{step}' cannot be looked up inside a {type(container).__name__}")


def apply_edits(data: dict, edits: list[FieldEdit]) -> dict:
    """Return a copy of `data` with each edit applied.

    A path that does not already resolve is an error rather than a silent no-op. On a dumped
    extract every field is present — absent values are null, not missing keys — so an
    unresolvable path means the model addressed something that isn't there, which is exactly
    the mistake worth catching rather than swallowing.
    """
    patched = copy.deepcopy(data)

    for edit in edits:
        steps = [s for s in edit.path.split(".") if s != ""]
        if not steps:
            raise PatchError(f"{edit.path!r} is not a usable path")

        container = patched
        for step in steps[:-1]:
            container = _resolve_step(container, step, edit.path)

        last = steps[-1]
        if isinstance(container, list):
            if not last.lstrip("-").isdigit():
                raise PatchError(f"{edit.path}: '{last}' is not a list position")
            index = int(last)
            if not -len(container) <= index < len(container):
                raise PatchError(
                    f"{edit.path}: position {index} is out of range, there are "
                    f"{len(container)} items"
                )
            container[index] = edit.value
        elif isinstance(container, dict):
            if last not in container:
                raise PatchError(f"{edit.path}: '{last}' is not a field here")
            container[last] = edit.value
        else:
            raise PatchError(
                f"{edit.path}: cannot set '{last}' inside a {type(container).__name__}"
            )

    return patched
