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

**Process all sessions in a directory:**

```bash
traininglogs log inputs/programs/<slug>/phase_N/week_N/
```

**Process a week by program/phase/week flags:**

```bash
traininglogs log --program <name> --phase <n> --week <n>
```

Add `--publish` to also push the updated dashboard to the website.

**Validate a file without writing to the DB:**

```bash
traininglogs validate inputs/programs/<slug>/phase_N/week_N/<session>.md
```

**Start the API:**

```bash
uvicorn traininglogs.api.app:app --reload
```

API is available at `http://localhost:8000`. All requests require `X-Api-Key` header.

**Run tests:**

```bash
.venv/bin/pytest tests/
```

Tests require both Postgres instances running (`docker compose up -d`).
