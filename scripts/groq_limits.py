"""Show the current Groq rate limits and how much of each is left.

Groq reports its limits in response headers on every call, including the 429 that tells you
you've run out. This makes one deliberately tiny request and prints them, so you can tell a
per-minute window (which refills in seconds) from a daily allowance (which does not).

Usage:
    .venv/bin/python scripts/groq_limits.py

Costs nothing -- Groq's free tier is free, and the request is a handful of tokens.
"""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(str(PROJECT_ROOT / ".env"))

import os  # noqa: E402

import groq  # noqa: E402

MODEL = "openai/gpt-oss-120b"

# Groq names these the same way OpenAI does. Requests and tokens are metered separately, and
# each has its own window -- which is why you can have requests left and no tokens, or the
# reverse.
HEADERS = [
    ("x-ratelimit-limit-requests", "requests allowed"),
    ("x-ratelimit-remaining-requests", "requests left"),
    ("x-ratelimit-reset-requests", "requests reset in"),
    ("x-ratelimit-limit-tokens", "tokens allowed"),
    ("x-ratelimit-remaining-tokens", "tokens left"),
    ("x-ratelimit-reset-tokens", "tokens reset in"),
]


def main() -> int:
    if not os.environ.get("GROQ_API_KEY"):
        print("GROQ_API_KEY is not set in .env")
        return 1

    client = groq.Groq(api_key=os.environ["GROQ_API_KEY"])
    print(f"model: {MODEL}\n")

    try:
        response = client.chat.completions.with_raw_response.create(
            model=MODEL,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
        )
        headers = response.headers
        print("request succeeded — you are not currently rate limited.\n")
    except groq.RateLimitError as exc:
        headers = getattr(exc.response, "headers", {}) or {}
        print("currently RATE LIMITED. Groq's own message:\n")
        # The body names which limit was hit and when it frees up -- the part our eval output
        # truncates.
        print(f"  {exc}\n")
    except Exception as exc:  # noqa: BLE001
        print(f"could not reach Groq: {type(exc).__name__}: {exc}")
        return 1

    print(f"{'limit':<22} {'value':>14}")
    print("-" * 38)
    found = False
    for key, label in HEADERS:
        value = headers.get(key)
        if value is not None:
            found = True
            print(f"{label:<22} {value:>14}")
    if not found:
        print("  (no rate-limit headers returned)")

    print()
    print("Reading these: a reset measured in seconds is a per-minute window and refills on its")
    print("own. One measured in hours is a daily allowance -- testing is done until it resets,")
    print("and pacing will not help.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
