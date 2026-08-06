"""Strict tool use: the tool definitions we send set `strict: true`, which constrains the
model's sampling to the schema's grammar. A tool call that omits a required field or mistypes
one cannot be generated at all.

This is prevention rather than recovery. On 2026-08-06 five workers returned `{"number": 1}`
with `name` missing; under strict mode that output is unreachable. The retry loop still exists
for what strict mode cannot judge — whether the call is *meaningful* — which is the job of
ExerciseExtract's own validation.

The API rejects an unsupported schema with a 400 rather than degrading quietly, so the test that
our real schemas stay inside the supported subset is a guard against a silent break the day
someone adds a constrained field.
"""
from __future__ import annotations

from typing import Any

import pytest

from traininglogs.agent.providers import strict_schema
from traininglogs.agent.schemas import ExerciseExtract, ExerciseSplit, SessionShellExtract

# Rejected by the grammar compiler. Pydantic emits these for ge/le/min_length/max_length/regex
# and for some `format`s, so a field gaining one of those constraints silently breaks strict mode.
UNSUPPORTED_KEYWORDS = {
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "minLength", "maxLength", "pattern", "minItems", "maxItems", "format",
}

LIVE_SCHEMAS = [ExerciseSplit, SessionShellExtract, ExerciseExtract]


def _walk(node: Any, path: str = ""):
    """Yield (path, node) for every dict in the schema."""
    if isinstance(node, dict):
        yield path, node
        for key, value in node.items():
            yield from _walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _walk(value, f"{path}[{i}]")


def _objects(schema: dict):
    return [(p, n) for p, n in _walk(schema) if n.get("type") == "object" and "properties" in n]


class TestStrictSchema:
    def test_every_object_is_closed(self) -> None:
        """`additionalProperties: false` is the one thing strict mode requires that Pydantic
        does not emit. It must reach nested definitions too, not just the root."""
        out = strict_schema(ExerciseExtract.model_json_schema())
        objects = _objects(out)
        assert len(objects) >= 2, "expected the root and the nested SetExtract definition"
        for path, node in objects:
            assert node["additionalProperties"] is False, f"{path or '<root>'} is still open"

    def test_the_input_schema_is_not_mutated(self) -> None:
        """The caller's schema is reused across calls; editing it in place would leak."""
        original = ExerciseExtract.model_json_schema()
        before = repr(original)
        strict_schema(original)
        assert repr(original) == before

    def test_non_object_nodes_are_left_alone(self) -> None:
        schema = {"type": "object", "properties": {"n": {"type": "integer"}}}
        out = strict_schema(schema)
        assert out["properties"]["n"] == {"type": "integer"}


class TestLiveSchemasStayStrictCompatible:
    @pytest.mark.parametrize("model", LIVE_SCHEMAS, ids=lambda m: m.__name__)
    def test_no_unsupported_keywords(self, model) -> None:
        found = [
            f"{path}.{key}"
            for path, node in _walk(model.model_json_schema())
            for key in UNSUPPORTED_KEYWORDS & node.keys()
        ]
        assert not found, (
            f"{model.__name__} uses schema keywords strict mode rejects: {found}. "
            "The API answers a 400, so every call with this schema would fail."
        )

    @pytest.mark.parametrize("model", LIVE_SCHEMAS, ids=lambda m: m.__name__)
    def test_references_are_internal_and_non_recursive(self, model) -> None:
        schema = model.model_json_schema()
        refs = [n["$ref"] for _, n in _walk(schema) if "$ref" in n]
        assert all(r.startswith("#/") for r in refs), f"external $ref in {model.__name__}: {refs}"

        # A definition that reaches itself is a recursive schema, which has no finite grammar.
        defs = schema.get("$defs", {})
        for name, body in defs.items():
            reached = {n["$ref"].split("/")[-1] for _, n in _walk(body) if "$ref" in n}
            assert name not in reached, f"{model.__name__}.{name} is recursive"
