# traininglogs

A personal training log system. Write workouts in markdown, process them into a structured database, query via a REST API, and view a static dashboard.

See [docs/architecture.md](docs/architecture.md) for a full reference.

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

**Process a training week** (parses markdown, inserts to DB, commits, rebuilds dashboard):

```bash
traininglogs log --phase <n> --week <n>
```

Input files must be in `input_training_logs_md/phase <n> week <n>/*.md`.

Add `--publish` to also push the updated dashboard to the website.

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
