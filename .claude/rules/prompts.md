---
paths:
  - "src/traininglogs/agent/prompts.py"
  - "src/traininglogs/agent/schemas.py"
---

# Prompts and the AI's output schema

- An edit here makes every cached eval call a new paid call: the cache key hashes the whole
  request (`scripts/eval_ab.py`). Batch prompt changes and measure once.
- `strict: true` stays off. It enforces property order and truncates output
  (`tests/test_agent_no_strict_tool_use.py`).
- Try structural changes on Groq first: it's free.
