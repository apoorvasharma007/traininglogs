# traininglogs

A personal training log system. Write workouts in markdown, process them into a structured database, query via a REST API, and view a static dashboard.

See [docs/design.html](docs/design.html) for the full technical reference.

---

## Setup

**Requirements:** Python 3.10+, Docker

```bash
# 1. Create venv and install
python -m venv .venv
.venv/bin/pip install -e .

# 2. Configure environment
cp .env.example .env
# Edit .env — set DATABASE_URL and API_KEY

# 3. Start Postgres
docker compose up -d
```

---

## Usage

**Process a single session file** (parses markdown, inserts to DB, commits, rebuilds dashboard):

```bash
traininglogs log inputs/programs/<slug>/phase_N/week_N/<session>.md
```

Session IDs are derived from the session's content and date, not the file path — the same
text submitted twice (from a file or otherwise) raises an error rather than silently creating
a duplicate. Editing a file's content and re-running produces a new session, not an update in
place — fix the date and re-run if you hit a collision you didn't expect.

**Process all sessions in a directory:**

```bash
traininglogs log inputs/programs/<slug>/phase_N/week_N/
```

**Process a week by program/phase/week flags:**

```bash
traininglogs log --program <name> --phase <n> --week <n>
```

**Validate a file without writing to the DB:**

```bash
traininglogs validate inputs/programs/<slug>/phase_N/week_N/<session>.md
```

**Run the app locally** (API and web UI, one process):

```bash
uvicorn traininglogs.api.app:app --reload
```

Open `http://localhost:8000/` for the web UI. API requests need the `X-Api-Key` header.

**Run tests:**

```bash
.venv/bin/pytest tests/
```

Tests require both Postgres instances running (`docker compose up -d`).

---

## Deploy

The app runs on Google Cloud Run: https://traininglogs-875429444117.us-east1.run.app

- **Infrastructure** is Terraform in [`infra/`](infra/README.md) — the layout, the one manual
  step, and how to plan/apply each layer.
- **Shipping** is automatic: merge `dev` into `main`. CI runs the tests and Terraform checks; CD
  then waits for approval in the `prod` GitHub environment, applies the app layer, builds the
  image and rolls Cloud Run onto it.
- **Secrets** (`database-url`, `api-key`, `anthropic-api-key`) live in Secret Manager. Add a new
  value with `gcloud secrets versions add <name> --data-file=-` or in the console; instances
  that start afterwards use it.
