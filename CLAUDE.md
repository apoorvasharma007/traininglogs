# traininglogs

## Vision

A personal training log system where you describe your workout in natural language, an AI agent maps it to a strict structured schema, stores it in a database, and serves it to a dashboard on your website.

Capture happens offline during the workout (draft saved locally in a PWA). Processing happens post-workout — AI maps the draft to the schema, asks clarifying questions if needed, then saves to DB.

---

## Architecture

```
PWA (mobile, offline-first)
  → capture free-form notes during workout, saved as local draft
  → on reconnect: send draft to AI agent

AI Agent (Claude Haiku 4.5)
  → maps draft to TrainingSession Pydantic model
  → asks clarifying questions if mapping is incomplete
  → confirms with user, then saves to DB

PostgreSQL
  → structured storage (sessions, exercises, sets)

FastAPI
  → REST API serving session data

Dashboard (apoorvasharma7.com)
  → static site, rebuilt on demand by a script that pulls from the API
```

**Key decisions:**
- Schema source of truth: Pydantic models (migrated from dataclasses when agent is built)
- JSON is downstream: output of `model.model_dump()`, used for DB and API
- Capture and AI processing are decoupled — no live API calls during workout
- DB runs locally via Docker Compose; deploy to Supabase free tier when remote access is needed
- No ORM — raw SQL with psycopg2, add tools only when there's a real pain point
- Dashboard is Hugo static site, rebuilt from a script (cron or manual), not a dynamic app

---

## Branching Strategy

```
main  ←  stable, current markdown parser, never touched during new development
  └── dev  ←  integration branch for all new work
        ├── feature/postgres-schema
        ├── feature/import-json-to-db
        ├── feature/fastapi
        └── feature/agent  (Track B, later)
```

- All feature branches cut from `dev`, merged back to `dev`
- `dev` merges to `main` only when the new version is production-ready and intentionally cuts over
- `main` remains untouched until that decision is made

---

## Roadmap

### Track A — Storage & Retrieval (current focus)

- [ ] Create `dev` branch
- [ ] Docker Compose with Postgres
- [ ] Design and create DB schema (sessions, exercises, working_sets, warmup_sets)
- [ ] Import existing JSON output files into DB
- [ ] FastAPI scaffold (`src/api/`)
- [ ] `GET /sessions` — list sessions (filters: phase, week, date range)
- [ ] `GET /sessions/{id}` — session detail
- [ ] `GET /exercises/{name}/history` — weight and reps over time
- [ ] API key auth (single key, just you)
- [ ] Tests for DB layer (real test DB via Docker, no mocks)
- [ ] Tests for API endpoints

### Track B — AI Agent (after Track A is stable)

- [ ] Migrate dataclass models → Pydantic models
- [ ] Add `anthropic` SDK dependency
- [ ] Structured extraction: send session draft + schema, get validated model back
- [ ] Clarification loop: ask targeted questions if extraction is incomplete
- [ ] Confirmation step: show parsed summary, user confirms before saving
- [ ] Wire agent → DB insert
- [ ] Tests for agent logic (mocked Claude responses)
- [ ] CLI entrypoint: `traininglogs agent`

### Track C — Dashboard (after Track A, design TBD)

- [ ] Decide approach (Hugo data files vs separate frontend)
- [ ] Script: fetch from API → generate static files → trigger Hugo rebuild
- [ ] Session list, session detail, exercise history chart
- [ ] Deploy and link from apoorvasharma7.com

---

## Current State (April 2026)

| Component | Status |
|---|---|
| Markdown → JSON parser | Working (on main) |
| Dataclass models + validation | Working and tested (on main) |
| JSON-on-disk output | Working (on main) |
| Pydantic models | Not started |
| PostgreSQL | Not started |
| FastAPI | Not started |
| AI agent | Not started |
| Dashboard | Not started |

---

## Dev Best Practices

### Branching

- `main` is always stable. Never commit directly to `main` during new development.
- `dev` is the integration branch. All feature branches cut from `dev`.
- Branch naming: `feature/<short-description>`, `fix/<short-description>`, `chore/<short-description>`
- One feature or fix per branch. Keep branches small and focused.
- Open a PR to merge into `dev`. Squash merge to keep history clean.

### Commits

- Small, atomic commits. Each commit leaves the codebase working.
- Format: `<type>: <short description>`
  - Types: `feat`, `fix`, `test`, `refactor`, `chore`, `docs`
  - Examples: `feat: add sessions table schema`, `fix: handle missing RPE field`
- No unrelated changes bundled in one commit.

### Testing

- Every new function, model, or endpoint gets a test before the PR merges.
- Tests in `tests/` mirroring `src/` structure.
- Run `pytest tests/` before opening any PR.
- DB tests use a real test database (Docker), never mocks.
- Agent tests use mocked Claude responses, never real API calls.

### Workflow for every change

```
1. Pull latest dev
2. Cut feature branch: git checkout -b feature/<name>
3. Make the smallest possible working change
4. Write or update tests
5. Run pytest locally — must pass
6. Commit with descriptive message
7. Push and open PR into dev
8. Merge when green
```

### Environment

- `.env` for secrets (API keys, DB URL) — never committed
- `.env.example` documents all required vars with placeholder values

---

## Project Layout (target)

```
src/traininglogs/
  models/      — dataclass models (current) → Pydantic models (Track B)
  agent/       — Claude API integration (Track B)
  db/          — Postgres layer: schema, insert, fetch
  api/         — FastAPI app and route handlers
  parser/      — legacy markdown parser (main only)
  processor/   — legacy CLI (main only)
tests/
  test_models.py
  test_db.py
  test_api.py
  test_agent.py       (Track B)
docker-compose.yml
.env.example
.github/
  workflows/
    ci.yml
```

---

## Working Conventions

- Python 3.10+, PEP 8, type hints on all functions
- No unnecessary abstractions — solve the current problem only
- No ORM unless there is a real pain point that justifies it
- Do not change field names without explicit instruction — DB schema and API depend on them
- Validation errors raise `TrainingLogValidationError`

## Commands

```bash
# Install
pip install -e .

# Run tests
pytest tests/

# Start local Postgres
docker compose up -d

# Current CLI (markdown parser, main only)
traininglogs --phase 3 --week 5
```
