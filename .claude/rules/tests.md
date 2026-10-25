---
paths:
  - "tests/**"
---

# Tests

- Tests that touch the database use the real test database, never mocks. Why: the owner and
  row-level checks in `src/traininglogs/db/migrations/` only fail against real Postgres.
- Mock only the paid model provider, as `tests/test_agent_provider_calls.py` does.
- A new Pydantic model gets tests for valid construction, each validator's accept and reject case,
  and a `model_dump(mode="json")` round trip.
