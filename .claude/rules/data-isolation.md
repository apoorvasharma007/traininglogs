---
paths:
  - "src/traininglogs/api/**"
  - "src/traininglogs/db/**"
  - "src/traininglogs/ingest/**"
---

# Each person's data is theirs alone

- A function that reads or writes a person's data takes the owner (`user_id`) and filters by it.
  The database also refuses a row whose owner differs from its parent's.
- A new endpoint that names a thing by id goes into `tests/test_isolation.py`. Its guard test fails
  otherwise.
