# Code Walkthrough: traininglogs

A React + FastAPI + PostgreSQL app for strength training tracking with AI-powered note extraction.

## Architecture Overview

### Deployment Architecture

```
                  PRODUCTION (Google Cloud)                   LOCAL DEVELOPMENT
                  
User Browser  →  Cloud Run (FastAPI container)  OR  →  localhost:8000 (dev server)
                        ↓
              Cloud SQL (PostgreSQL)          OR  →  Docker Postgres (port 5433)
                        ↓
Supabase Auth (JWT verification)
                        ↓
AI Providers (Anthropic, Groq API)
```

### Components

- **Frontend**: React (TypeScript) built to `frontend/dist/`, served by FastAPI
- **Backend**: FastAPI Python web framework
  - Production: Containerized on Google Cloud Run
  - Development: Local Uvicorn server (port 8000)
- **Database**: PostgreSQL
  - Production: Google Cloud SQL (managed)
  - Development: Docker container (port 5433)
- **Authentication**: Supabase JWT tokens verified on every request
- **AI Integration**: Anthropic and Groq API calls

---

## Backend Overview

### Entry Point: `src/traininglogs/api/app.py`

The FastAPI application defines all HTTP endpoints:
- Session logging: `POST /sessions`, `GET /sessions`
- AI-powered extraction: `POST /inputs`, `POST /extractions/{id}/confirm`
- Programs and workouts: `GET/POST/PATCH/DELETE /programs`, `/workouts`
- Progress tracking: `GET /progress/lifts`

**Key pattern**: Every endpoint takes `user: str = Depends(_user)` to ensure a person only sees their own data.

### Database Layer

#### `src/traininglogs/db/fetch.py` — Reading Data
- `get_sessions()` — List sessions with optional filters (phase, week, date range)
- `get_session()` — Full session detail: exercises, warmup/cooldown, all sets
- `get_exercise_history()` — All reps of one exercise across sessions
- `get_working_set_rows()` — Input to the Progress view (4-week trend)
- `get_last_exercises()` — Recent performance of each named exercise

**Pattern**: Every function filters by `user_id`. No SQL injection: all parameters use psycopg2's `%s` placeholders.

#### `src/traininglogs/db/insert.py` — Writing Data
- `insert_input()` — Store a raw note, exactly as written
- `insert_card()` — Save the AI's reading of a note
- `insert_session()` — Save the whole session: exercises, sets, movements
- `confirm_card()` — Mark a pending extraction confirmed
- `user_exercise_ids()` — Create or fetch exercise IDs by name

**Key invariant**: One transaction saves the whole session or none. If the dedup key matches (same date + text hash), `INSERT ... ON CONFLICT DO NOTHING` returns null instead.

#### `src/traininglogs/db/programs.py` — Programs and Workouts
- `list_programs()` — All programs with workouts, followed one first
- `create_program()` — New program with initial workouts in one transaction
- `follow_program()` / `unfollow_program()` — Switch the followed program
- `add_workout()` — Add a workout after the last one
- `reorder_workouts()` — Renumber all workouts in new order
- `set_workout_exercises()` — Replace a workout's exercise plan
- `archive_program()` / `archive_workout()` — Mark as deleted (soft delete)
- `deload_status()` — Days since deload started, whether one is due

**Convention**: Position numbers (1..n) stay dense. Archiving a workout renumbers the rest.

#### `src/traininglogs/db/ids.py` — UUID v7 IDs
- `new_id()` — Generate UUID v7 with millisecond timestamp + counter
- Ensures IDs sort in insertion order (first 48 bits are time in ms)
- Counter handles up to 4,096 IDs/ms in a single process

### Models

#### `src/traininglogs/models/models.py` — Session Structure
- `TrainingSession` — The complete session sent from the app or AI
- `Exercise` — One exercise: name, sets, warmup_sets, goals
- `WorkingSet` — Weight, reps (full/partial), RPE, notes
- `WarmupSet` — Lighter sets before working sets
- `Rest` — How much rest between sets (minutes and seconds)

**Validators**: `rep_count` must have `full` or `partial`; unilateral (`left`/`right`) reps check that exactly two sides exist.

### API Schemas

#### `src/traininglogs/api/schemas.py` — Request/Response Models
- `SessionSummary` — List view (date, program, exercises, duration)
- `SessionDetail` — Full view (with all sets and goals)
- `ExerciseOut` — Exercise with its sets and form cues
- `LiftsOut` — Progress view: key lifts and trends
- `ManualSessionIn` — User-logged session (no AI)
- `CaptureIn/Out` — Note upload and extraction response

### Authentication

#### `src/traininglogs/api/auth.py` — Sign-in and Authorization
- `verify(token)` — Decode JWT from Supabase, check signature and expiry
- `user_for(conn, claims)` — Find or create user record; update `last_seen_at`
- `bearer(authorization)` — Extract Bearer token from header

**Flow**: Token → Supabase public keys (cached, rotated if needed) → Verified claims → User ID

### AI and Extraction

#### `src/traininglogs/agent/schemas.py` — Extraction Schemas
- `TrainingLogLLMExtract` — The shape the AI returns: focus, exercises, sets
- Validators parse text like `"5x5 @ 225"` into structured `reps` and `weight`
- `uncertain_fields` — Which fields the AI wasn't sure about

#### `src/traininglogs/agent/extraction.py` — AI Reading
- `extract()` — Run the AI on a stored note, save the reading as a card

#### `src/traininglogs/agent/providers.py` — LLM Providers
- `AnthropicProvider` — Anthropic API calls with token/cost tracking
- `GroqProvider` — Groq API (for eval, cheaper)
- `.calls` — List of {step, model, cost_usd, input_tokens, output_tokens}

#### `src/traininglogs/agent/prompts.py` — System Prompts
- `SPLITTER_SYSTEM_PROMPT` — Tell the AI to segment a note into sessions
- `EXTRACTOR_SYSTEM_PROMPT` — Extract one session's structure

#### `src/traininglogs/agent/llm_extract_validator.py` — Corrections
- `apply_correction()` — User typed a fix; re-run AI to apply it
- Updates the card without saving; user confirms after

#### `src/traininglogs/agent/validation_card_builder.py` — UI for Validation
- `ValidationCardBuilder` — Turn extracted JSON into UI fields (readonly or editable)
- Each field shows: value, source (AI or user), uncertain flag

### Ingestion Flow

#### `src/traininglogs/ingest/extract.py`
- `extract()` — Store note → Run AI → Save card with status 'pending'
- Never waits on the user; confirmation is a separate call

#### `src/traininglogs/ingest/confirm.py`
- `confirm()` — Mark card confirmed → Save session
- Dedup on `(user_id, session.session_id)` key: same date + text hash

#### `src/traininglogs/ingest/manual.py`
- `save_manual_session()` — Session logged in the app, no AI
- Same dedup and session save as `confirm()`

### Analytics

#### `src/traininglogs/analytics/progress.py`
- `lift_summaries()` — Key lifts (configurable), then others trained 3+ times
- Each: latest and best 1RM, 4-week trend
- `lift_detail()` — One lift's full history with records and goal

#### `src/traininglogs/analytics/strength.py`
- Estimated max per set: Epley formula for reps/RPE
- Personal records: heaviest weight and best reps at each weight
- 4-week trend: workload and avg est. 1RM

#### `src/traininglogs/analytics/key_lifts.py`
- Default key lifts (bench, squat, deadlift) and aliases (e.g., "bench press" → "bench")

---

## Frontend Overview

### Structure
```
frontend/src/
├── screens/        Top-level pages (routed)
├── components/     Reusable UI blocks
├── lib/            Utilities, API client, hooks
└── index.css       Global styles
```

### Main Screens

#### `frontend/src/screens/Train.tsx`
- Add exercises, sets, warmup/cooldown
- Save manually or upload as notes to AI
- Runs on the followed program

#### `frontend/src/screens/LogFromNotes.tsx`
- Paste a training note
- View AI extraction card
- Fix errors in the card
- Confirm to save session

#### `frontend/src/screens/Progress.tsx`
- Key lifts: latest, best, 4-week trend chart
- Other lifts trained 3+ times
- Click to see full history

#### `frontend/src/screens/Lift.tsx`
- One lift's session list
- Records (heaviest, best reps)
- Goal progress

#### `frontend/src/screens/History.tsx`
- All sessions, newest first
- Filter by program, phase, week, date
- Click to view details

#### `frontend/src/screens/Programs.tsx`
- List all programs
- Follow/unfollow
- Archive programs

#### `frontend/src/screens/Program.tsx`
- Edit program name, deload days
- Manage workouts (add, rename, reorder)
- Edit each workout's exercises

#### `frontend/src/screens/SessionView.tsx`
- Full session detail
- Exercises with all sets
- Program context (name, week, phase)

#### `frontend/src/screens/Settings.tsx`
- AI usage cost
- Sign out

### Key Components

#### `frontend/src/components/SetSheet.tsx`
- Modal for editing one set
- Weight, reps (full/partial), RPE, rest
- Unilateral reps (left/right)

#### `frontend/src/components/BottomBar.tsx`
- Fixed action bar at bottom of each screen
- Primary action (e.g., "Save Session")

#### `frontend/src/components/Sheet.tsx`
- Drawer modal (slides from bottom)
- Resizable, scrollable content

#### `frontend/src/components/DragList.tsx`
- Reorder items with drag-and-drop

#### `frontend/src/components/EffortBars.tsx`
- RPE visualization (1-10 scale)

#### `frontend/src/components/LineChart.tsx`
- Simple chart for trends
- Used in Progress and Lift screens

### Library Code

#### `frontend/src/lib/api.ts`
- `apiClient` — Fetch wrapper with auth headers
- Endpoints: `/sessions`, `/progress/lifts`, `/extractions`, etc.

#### `frontend/src/lib/hooks.ts`
- `useAuth()` — Sign-in state and user ID
- `useSession()` — Fetch one session by ID
- `useSessions()` — List sessions with filters
- `useExtractionCard()` — Fetch pending extraction
- All use React Query (`@tanstack/react-query`) for caching and refetch

#### `frontend/src/lib/format.ts`
- `formatDate()` — Date display
- `formatWeight()` — Weight with unit (kg/lb)

---

## Key Patterns

### Session Deduplication
A session is uniquely identified by `(user_id, dedup_key)`:
- `dedup_key = session.session_id` (the date + hash of the input text)
- Logging the same note twice returns the existing session, not a new one
- `INSERT ... ON CONFLICT DO NOTHING RETURNING id` — atomically safe

### Row-Level Security
- Every table has a `user_id` column
- Every query filters `WHERE user_id = %s`
- Database foreign keys enforce that rows under a user link only to their own rows
- API endpoints take `user: str = Depends(_user)` and pass it everywhere

### State Between Edits
- AI extraction fixes keep state entirely on the client
- `body.extract` carries the current state between `/correct` and `/edit` calls
- Server doesn't store partial edits; only confirmed extractions are saved
- Canceling the fix discards all unsaved changes

### Soft Deletes
- Programs and workouts are archived, not deleted
- `archived_at IS NULL` filters them out of queries
- Keeps the dedup history and cost records

### Connection Pool Management
- The server uses `psycopg2.pool.SimpleConnectionPool` (1–10 connections)
- Idle connections (60+ seconds) are probed with `SELECT 1` before reuse
- Supabase closes idle connections; the probe detects this and replaces the connection
- Every request rolls back its transaction after responding (even GETs)

---

## Testing

### Backend Tests: `tests/`
- `test_sessions.py` — Save, list, fetch sessions
- `test_programs.py` — Create, follow, archive programs
- `test_isolation.py` — Verify data isolation (one user can't see another's data)
- `test_extraction.py` — AI reading and corrections
- Uses a local Postgres instance (Docker, port 5433)

### Frontend Tests: `frontend/src/**/*.test.tsx`
- Component unit tests with `@testing-library/react`
- Mock API responses

### Running Tests
```bash
# Backend
.venv/bin/pytest tests/

# Frontend
cd frontend && npm test
```

---

## Deployment

### Technology Stack
- **Framework**: FastAPI (Python web framework)
- **Container runtime**: Google Cloud Run (serverless, managed by Terraform)
- **Database**: Google Cloud SQL (PostgreSQL) + Supabase auth layer
- **Infrastructure as Code**: Terraform (`infra/`)
- **CI/CD**: GitHub Actions

### Local Development
```bash
# Build frontend
cd frontend && npm ci && npm run build && cd ..

# Start FastAPI server locally (for development only)
DATABASE_URL="..." .venv/bin/uvicorn traininglogs.api.app:app --reload
```

- App: `http://localhost:8000/` (local only)
- API: `http://localhost:8000/` (same origin)
- This is a development server; production uses Cloud Run

### Production Deployment
- **Environment**: Google Cloud Run (serverless container)
- **Branch flow**: 
  - `main` → Production (GCP region us-west1)
  - `dev` → Staging (separate Cloud Run instance)
- **Infrastructure**: Managed by Terraform in `infra/`
  - Cloud Run service configuration
  - Cloud SQL PostgreSQL instance
  - Supabase auth project
  - Environment secrets in Google Cloud Secret Manager

### CI/CD Pipeline
- GitHub Actions in `.github/workflows/`
- Tests run on every push
- Merge to `dev` deploys to staging automatically
- Merge to `main` requires manual approval in GitHub (prod environment)
- Terraform applies infrastructure changes on deploy
- CI then deploys the container to Cloud Run

---

## Code Organization

### Naming Conventions
- **Python functions**: `snake_case`
- **React components**: `PascalCase`
- **Database columns**: `snake_case`
- **Pydantic models**: `PascalCase`
- **Exercise names**: Normalized on `name_key` (lowercase, single spaces)

### Module Docstrings
Every module has a one-sentence docstring describing its purpose:
- `api/app.py` — FastAPI application
- `db/fetch.py` — Reading people's data
- `models/models.py` — Pydantic models for training sessions
- `agent/schemas.py` — AI extraction schemas
- Similar for all other modules

### Function Docstrings
Public functions have docstrings; private functions (prefixed `_`) have one-line comments where complex. Trivial getters/setters are left undocumented.

---

## Critical Files and Links

| File | Purpose |
|------|---------|
| [api/app.py](https://github.com/apoorvasharma007/traininglogs/blob/main/src/traininglogs/api/app.py) | FastAPI endpoints |
| [api/auth.py](https://github.com/apoorvasharma007/traininglogs/blob/main/src/traininglogs/api/auth.py) | Supabase JWT verification |
| [db/fetch.py](https://github.com/apoorvasharma007/traininglogs/blob/main/src/traininglogs/db/fetch.py) | Session and exercise queries |
| [db/insert.py](https://github.com/apoorvasharma007/traininglogs/blob/main/src/traininglogs/db/insert.py) | Session and card saving |
| [db/programs.py](https://github.com/apoorvasharma007/traininglogs/blob/main/src/traininglogs/db/programs.py) | Programs and workouts |
| [models/models.py](https://github.com/apoorvasharma007/traininglogs/blob/main/src/traininglogs/models/models.py) | Session structure |
| [agent/extraction.py](https://github.com/apoorvasharma007/traininglogs/blob/main/src/traininglogs/agent/extraction.py) | AI note reading |
| [agent/providers.py](https://github.com/apoorvasharma007/traininglogs/blob/main/src/traininglogs/agent/providers.py) | LLM API clients |
| [analytics/progress.py](https://github.com/apoorvasharma007/traininglogs/blob/main/src/traininglogs/analytics/progress.py) | Progress view data |
| [App.tsx](https://github.com/apoorvasharma007/traininglogs/blob/main/frontend/src/App.tsx) | React routing |
| [Train.tsx](https://github.com/apoorvasharma007/traininglogs/blob/main/frontend/src/screens/Train.tsx) | Session logging |
| [Progress.tsx](https://github.com/apoorvasharma007/traininglogs/blob/main/frontend/src/screens/Progress.tsx) | Strength trends |

---

## Example: Logging a Session

### Step 1: User enters data in Train.tsx
```tsx
// Train.tsx: useSession hook fetches or creates a draft session
const [session, setSession] = useState<TrainingSession>({
  date: today(),
  exercises: [{
    name: 'Squat',
    sets: [{ weight_kg: 225, rep_count: { full: 5 } }],
  }],
})
```

### Step 2: POST /sessions saves manually
```python
# app.py: /sessions endpoint
session_id, created = save_manual_session(conn, user, body.model_dump())
return SessionSaved(session_id=session_id, created=created)
```

### Step 3: insert.py saves to database
```python
# insert.py: insert_session()
# Dedup key = date + text hash (empty for manual)
# If exists, return None
# Else save session, exercises, sets in one transaction
```

### Step 4: GET /sessions returns the saved session
```python
# fetch.py: get_sessions()
# SELECT from workout_sessions, join exercises and sets
# Return list of SessionSummary
```

---

## Example: AI Note Extraction

### Step 1: User pastes a note (LogFromNotes.tsx)
```tsx
const upload = async (content: string) => {
  const res = await apiClient.post('/inputs', { content })
  // Returns: { raw_input_id, extraction_id }
}
```

### Step 2: POST /inputs stores note and runs AI (app.py)
```python
input_id = insert_input(conn, user, content)
card_id = extract(conn, user, input_id, date, provider)
# extract() → AnthropicProvider → AI reads note → save card
```

### Step 3: GET /extractions/{id} returns validation UI
```python
# app.py: get_extraction_card()
card = get_card(conn, user, card_id)
return ValidationCardBuilder().build(card['extract'])
```

### Step 4: User fixes and confirms (POST /extractions/{id}/confirm)
```python
# app.py: confirm_extraction_endpoint()
session_id = confirm(conn, user, card_id, final_extract)
# confirm() → insert_session() → save with dedup
```

---

## Common Tasks

### Add a new endpoint
1. Define Pydantic model in `api/schemas.py`
2. Add function in the appropriate `db/` module
3. Add `@app` route in `api/app.py`
4. Test in `tests/test_*.py`

### Add a new database table
1. Add schema to `db/schema.sql`
2. Run `apply_schema()` on startup or migration
3. Add fetch/insert functions in `db/`

### Add a new React screen
1. Create `frontend/src/screens/NewScreen.tsx`
2. Import in `App.tsx` and add a `<Route>`
3. Use `useAuth()` and `useSessions()` hooks for data
4. Style with CSS in `index.css` (locked design system)

### Change a prompt
1. Edit `agent/prompts.py`
2. Increment `PROMPT_VERSION` (affects eval cache key)
3. Run dry-run first: `scripts/eval_arms.py --dry-run`

---

## Notes for Developers

- **Queries**: Always use `%s` placeholders; never f-string SQL
- **Transactions**: GETs return early (no explicit commit); POSTs commit at the end
- **Errors**: 401 for auth, 404 for not found, 422 for validation, 502 for AI failures
- **Cost**: Check `get_ai_total_usd()` before major runs; note storage is cheap
- **Backwards compatibility**: Avoid renaming database columns and Pydantic fields
- **Design**: The app look is locked; propose visual changes first
