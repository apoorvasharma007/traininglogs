"""Guard against re-enabling grammar-constrained tool use (`strict: true`).

It looks like exactly the right fix for a model that omits a required field, and it was enabled
on 2026-08-06 for that reason. It made things far worse, because it also enforces the schema's
**property order**.

People write warmups above working sets — `### Warmup Notes` precedes `### Working Sets` — and
the model emits in document order: `name, warmup_notes, warmup_sets, sets`. The schema declares
`name, sets, warmup_sets, notes, warmup_notes`. Under the grammar those conflict: once
`warmup_notes` has been emitted, `sets` is behind the cursor and can never be produced. Whole
exercises came back as a name and nothing else.

Measured across the raw dumps of three runs:

    without strict   8 of 18 payloads out of schema order, all carrying their sets
    with strict      0 of 10 out of order, core accuracy 77.6% -> 31.4%

Reordering the fields would only move the problem — Groq's natural order was different again
(`name, notes, sets`), and photo/speech input won't follow the markdown layout at all.

The failure strict mode was meant to prevent is handled instead by validating inside the retry
loop (see test_agent_providers_retry.py), which costs one extra call on a rare bad payload
rather than silently truncating every good one.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from traininglogs.agent.providers import AnthropicProvider


def _tool_definition_sent() -> dict:
    """Make one call against a mocked client and return the tool definition it sent."""
    with patch("traininglogs.agent.providers.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        block = MagicMock()
        block.type = "tool_use"
        block.input = {"ok": True}
        block.id = "toolu_1"
        mock_client.messages.create.return_value = MagicMock(content=[block])
        mock_cls.return_value = mock_client

        schema = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
        AnthropicProvider().extract("text", schema, "sys", "tool", "desc")
        return mock_client.messages.create.call_args[1]["tools"][0]


class TestGrammarConstrainedDecodingStaysOff:
    def test_tool_definition_does_not_request_strict(self) -> None:
        assert "strict" not in _tool_definition_sent(), (
            "strict tool use enforces schema property order, which silently truncates any "
            "payload whose natural order differs — read this module's docstring before "
            "turning it back on."
        )

    def test_the_schema_is_sent_unmodified(self) -> None:
        """No `additionalProperties: false` injection either. That was only ever needed to
        satisfy strict mode, and closing the objects buys nothing without it."""
        sent = _tool_definition_sent()["input_schema"]
        assert "additionalProperties" not in sent
        assert sent == {"type": "object", "properties": {"a": {"type": "string"}},
                        "required": ["a"]}
