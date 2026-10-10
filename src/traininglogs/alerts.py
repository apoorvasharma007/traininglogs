"""Posts new feedback to Apoorva's Discord channel, through the webhook in DISCORD_WEBHOOK_URL.

Best effort: the feedback is already saved, so a failed or slow post (3 s at most) is only logged. Without the variable
(tests, a local server) nothing is sent. Mentions are switched off, so text like "@everyone" in a
message can't ping the server.
"""
from __future__ import annotations

import os

import httpx

KIND_LABEL = {"feature": "Feature request", "bug": "Problem", "other": "Other"}
DISCORD_LIMIT = 2000  # characters in one Discord message


def feedback_alert(kind: str, message: str, email: str | None, app_version: str | None) -> None:
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        return
    environment = os.environ.get("APP_ENVIRONMENT", "prod")
    prefix = "" if environment == "prod" else f"[{environment}] "
    text = f"{prefix}**{KIND_LABEL[kind]}** from {email or 'someone'} (version {app_version})\n{message}"
    try:
        httpx.post(url, json={"content": text[:DISCORD_LIMIT], "allowed_mentions": {"parse": []}}, timeout=3).raise_for_status()
    except httpx.HTTPError as exc:
        print(f"Discord feedback alert failed: {exc}", flush=True)
