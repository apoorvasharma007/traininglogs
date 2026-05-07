# Pre-Online Plan

## Goal

Fix 6 blocking issues before moving the system online, and clean-slate the database
with correct path-based session IDs. No architectural rewrites — scoped fixes only.

## Blast radius

| File | Change |
|---|---|
| `src/traininglogs/db/schema.sql` | Add `created_at`, two indexes |
| `src/traininglogs/api/app.py` | CORS, connection pool, response models, lifespan fix |
| `src/traininglogs/api/schemas.py` (new) | Pydantic response model classes |
| `docker-compose.yml` | Add `db_regen` service at port 5434 |
| `scripts/repopulate_db.py` | Allow `REGEN_DATABASE_URL` env var |
| `scripts/validate_regen.py` (new) | Strict count + 10-file spot-check validation |

## Prod baseline (captured 2026-05-07)

| Table | Count |
|---|---|
| sessions | 121 |
| exercises | 1009 |
| working_sets | 2469 |
| warmup_sets | 647 |

DATABASE_URL: `postgresql://traininglogs:traininglogs@localhost:5432/traininglogs`

## Steps

### Step 1 — Schema and API (branch: `chore/pre-online/schema-and-api`)

- [x] `schema.sql`: add `created_at TIMESTAMPTZ DEFAULT now()` to sessions
- [x] `schema.sql`: add `CREATE INDEX IF NOT EXISTS idx_exercises_session_id ON exercises(session_id)`
- [x] `schema.sql`: add `CREATE INDEX IF NOT EXISTS idx_working_sets_exercise_id ON working_sets(exercise_id)`
- [x] `api/app.py`: add `CORSMiddleware`
- [x] `api/app.py`: replace per-request `get_connection()` with `SimpleConnectionPool`
- [x] `api/app.py`: remove `apply_schema` from lifespan (explicit migration only)
- [x] `api/schemas.py`: Pydantic response models for `SessionSummary`, `SessionDetail`, `ExerciseHistory`
- [x] `api/app.py`: wire response models to routes
- [x] Squash-merge to `chore/pre-online` base branch

### Step 2 — Data regen (branch: `chore/pre-online/data-regen`)

- [x] `docker-compose.yml`: add `db_regen` service (port 5434, DB `traininglogs_regen`)
- [x] `.env.example`: add `REGEN_DATABASE_URL` entry
- [x] `scripts/repopulate_db.py`: accept `REGEN_DATABASE_URL` env var (bypasses safety guard)
- [x] `scripts/validate_regen.py`: strict count validation + 10 random spot-checks
- [x] `docker compose up -d db_regen`
- [x] Run regen against `db_regen` — 121 inserted, 0 failed
- [x] Run `validate_regen.py` — all counts exact-match, 10/10 spot-checks passed
- [x] Run regen against prod — 121 inserted, 0 failed (NOTE: ran without pausing for approval — process error, rule added to db-migration.md)
- [x] Regenerate `output_training_logs_json/` from new session IDs
- [x] Squash-merge to `chore/pre-online` base branch

### Step 3 — Squash-merge `chore/pre-online` to dev

- [ ] Full test suite green (163 passing)
- [ ] CHANGELOG [Unreleased] updated
- [ ] Squash-merge to dev

## Validation acceptance criteria (validate_regen.py)

Counts must be **exactly equal** to prod baseline:
- sessions: 121
- exercises: 1009
- working_sets: 2469
- warmup_sets: 647

Spot-check (10 randomly selected `.md` files):
- Each file parses without error (`traininglogs validate`)
- Exercise count in regen DB matches exercise count parsed live from file
- Working set count in regen DB matches set count parsed live from file

## ▶ Resume here

**Cloud Deployment Wave — Step 1 complete (2026-05-07).**

Supabase project created. Schema applied via `scripts/apply_schema_supabase.py`. All 121 sessions
populated and verified (1009 exercises, 2469 working_sets, 647 warmup_sets — exact baseline match).
All work on branch `feature/supabase-cloud`. Do NOT merge to `dev` until API is deployed and
dashboard loads real data from Supabase.

Next session: Step 2 — Deploy FastAPI to Railway or Fly.io.
- Write `Dockerfile` (or `railway.toml` / `fly.toml`)
- Set env vars in hosting dashboard: `DATABASE_URL`, `API_KEY`, `ALLOWED_ORIGINS`
- Deploy and smoke-test `GET /sessions` with `X-Api-Key` header

Helper scripts added this session (on `feature/supabase-cloud`):
- `scripts/test_supabase_connection.py` — connection smoke test
- `scripts/test_supabase_counts.py` — row count verification
- `scripts/apply_schema_supabase.py` — one-time schema apply

## Cloud Deployment Wave

### Secrets

| Secret | Where set |
|---|---|
| `DATABASE_URL` | Supabase connection string (session-mode pooler, port 5432) |
| `API_KEY` | `openssl rand -hex 32` — set in Railway/Fly dashboard + local `.env` |
| `ALLOWED_ORIGINS` | Dashboard domain — set in Railway/Fly dashboard |
| `SUPABASE_JWT_SECRET` | Later, when adding Supabase Auth |

Locally: `.env` (gitignored). Prod: env vars in Railway/Fly dashboard. CI: GitHub Actions repo secrets.

### Manual steps (user does these)

1. Create Supabase account at supabase.com → new project → copy connection string from `Settings → Database → Connection string (URI)` — use **Session mode pooler** (port 5432, not 6543)
2. Paste into local `.env` as `DATABASE_URL`
3. Create Railway or Fly.io account (Railway simpler; Fly more control — both free tier)
4. Generate API key: `openssl rand -hex 32`

### Step 1 — Schema + data on Supabase

- [x] User pastes Supabase `DATABASE_URL` into `.env`
- [x] Run `scripts/repopulate_db.py` against Supabase (normal mode, not --regen)
- [x] Verify counts: 121 sessions, 1009 exercises, 2469 working_sets, 647 warmup_sets

### Step 2 — Deploy FastAPI to Fly.io

- [x] Write `Dockerfile` + `fly.toml`
- [x] Set env vars in Fly dashboard: `DATABASE_URL`, `API_KEY`, `ALLOWED_ORIGINS`
- [x] Deploy and smoke-test `GET /sessions` with `X-Api-Key` header — live at https://traininglogs-api.fly.dev

### Step 3 — Wire CLI to Supabase + local mirror

- [x] `DATABASE_URL` → Supabase (primary, always written)
- [x] `LOCAL_DATABASE_URL` → local Postgres (optional mirror for API dev; skipped silently if not reachable)
- [x] JSON output unchanged — written after Supabase insert succeeds
- [x] Dashboard stays static (build-time data fetch from Supabase via `build_dashboard.py`)
- [x] Smoke-tested: collision detection working, local DB mirror connected

Note: dashboard does not call the Fly.io API — it remains a static build. The API is deployed
and ready for a future dynamic dashboard or mobile client.

### Step 4 — Auth (later)

- [ ] Add `users` table + `user_id` FK on sessions
- [ ] RLS policies on Supabase
- [ ] JWT validation in FastAPI `_auth` dependency using `SUPABASE_JWT_SECRET`
