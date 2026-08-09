"""Measure the exact token cost of each split-extraction call's prefix (system prompt + tool
schema) via Anthropic's count_tokens endpoint. Written for Step 8.5a of
archived/plans/orchestration-refactor-plan.md — replaces the char-count estimates in that plan with real
numbers, and settles whether the worker prefix clears Haiku 4.5's 4,096-token minimum
cacheable prefix.

Usage:
    .venv/bin/python scripts/measure_prefix_tokens.py

Requires ANTHROPIC_API_KEY. Makes one count_tokens call per prefix (cheap — no output tokens
generated — but a real API call against ANTHROPIC_API_KEY).
"""
from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import anthropic

from traininglogs.agent.extraction import (
    SEGMENT_TOOL_DESCRIPTION,
    SEGMENT_TOOL_NAME,
    SHELL_TOOL_DESCRIPTION,
    SHELL_TOOL_NAME,
    WORKER_TOOL_DESCRIPTION,
    WORKER_TOOL_NAME,
)
from traininglogs.agent.prompts import SHELL_SYSTEM_PROMPT, SPLITTER_SYSTEM_PROMPT, WORKER_SYSTEM_PROMPT
from traininglogs.agent.providers import DEFAULT_ANTHROPIC_MODEL
from traininglogs.agent.schemas import ExerciseExtract, ExerciseSplit, SessionShellExtract

HAIKU_MIN_CACHEABLE_TOKENS = 4096

PREFIXES = [
    ("Splitter", SPLITTER_SYSTEM_PROMPT, ExerciseSplit, SEGMENT_TOOL_NAME, SEGMENT_TOOL_DESCRIPTION),
    ("Shell", SHELL_SYSTEM_PROMPT, SessionShellExtract, SHELL_TOOL_NAME, SHELL_TOOL_DESCRIPTION),
    ("Worker", WORKER_SYSTEM_PROMPT, ExerciseExtract, WORKER_TOOL_NAME, WORKER_TOOL_DESCRIPTION),
]


def main() -> None:
    client = anthropic.Anthropic()

    print(f"Model: {DEFAULT_ANTHROPIC_MODEL}")
    print(f"Haiku 4.5 minimum cacheable prefix: {HAIKU_MIN_CACHEABLE_TOKENS} tokens\n")
    print(f"{'Call':<10} {'Prefix tokens':>15}")

    total = 0
    for name, prompt, schema_model, tool_name, tool_description in PREFIXES:
        result = client.messages.count_tokens(
            model=DEFAULT_ANTHROPIC_MODEL,
            system=prompt,
            tools=[
                {
                    "name": tool_name,
                    "description": tool_description,
                    "input_schema": schema_model.model_json_schema(),
                }
            ],
            messages=[{"role": "user", "content": "placeholder"}],
        )
        print(f"{name:<10} {result.input_tokens:>15}")
        total += result.input_tokens

        if name == "Worker":
            verdict = "CLEARS" if result.input_tokens >= HAIKU_MIN_CACHEABLE_TOKENS else "BELOW"
            margin = result.input_tokens - HAIKU_MIN_CACHEABLE_TOKENS
            print(
                f"  -> {verdict} the {HAIKU_MIN_CACHEABLE_TOKENS}-token cache minimum "
                f"(margin: {margin:+d} tokens)"
            )

    print(f"\nTotal prefix per single splitter+shell+1 worker call: {total} tokens")
    print("(A 6-exercise session sends the worker prefix 6 times, not once.)")


if __name__ == "__main__":
    main()
