---
name: setup
description: Set up this repo on a machine, fill in .env, run the app locally, or add or upgrade a Python package. Use before running the app or changing requirements.
---

# Local development

Python 3.12, the server's version (`.python-version`); on a Mac, `brew install python@3.12`.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.lock && .venv/bin/pip install --no-deps -e .
cp .env.example .env              # then fill it in, see below
docker compose up -d db_test      # Postgres for the tests, on port 5433
```

| `.env` variable | Needed for | |
|---|---|---|
| `DATABASE_URL` | the app | Required. Points at production; see the warning below. |
| `SUPABASE_URL` | the app | Required: the Supabase project whose sign-ins the server accepts. The app won't start without it. |
| `SUPABASE_PUBLISHABLE_KEY` | the app | Required: that project's publishable key, which the app signs in with. Public by design. The app won't start without it. |
| `ANTHROPIC_API_KEY` | extraction and typed corrections | Required |
| `ANTHROPIC_WORKSPACE_ID` | Anthropic keys not scoped to a workspace (`sk-ant-usr…`) | Required with such a key |
| `TEST_DATABASE_URL` | the tests | Defaults to the Docker database on port 5433 |
| `GROQ_API_KEY` | `eval_ab.py` comparing models | Optional |
| `ALLOWED_ORIGINS` | calling the API from a page on another origin | Optional; the app's own page doesn't need it |

Build the app once, then run it. One process serves the API and the app at `http://localhost:8000/`:

```bash
cd frontend && npm ci && npm run build && cd ..
```

```bash
DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/uvicorn traininglogs.api.app:app --reload
```

While changing the app, `cd frontend && npm run dev` serves it at `http://localhost:5173/` and
reloads on every save; it sends API calls to the server on port 8000.

Point `DATABASE_URL` at the test database like this when trying things out. Without it, the app
reads and writes production. Each Extract is a paid model call either way.

To try things on real data without touching production, copy it into a local dev database (this
only reads production) and run the app on port 8010 against the copy:

```bash
.venv/bin/python scripts/copy_prod_to_dev.py
DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_dev \
    .venv/bin/uvicorn traininglogs.api.app:app --port 8010
```

To run the tests, use `/verify`: it sets up a private test database first.

Package versions are locked. `requirements.lock` has the exact version of everything the server
installs, and `requirements-dev.lock` adds the test tools; the server build, CI and your machine
install from them, so all three run the same thing. To add or upgrade a package, change
`pyproject.toml`, then remake both files and commit them with the change:

```bash
.venv/bin/pip-compile --strip-extras --no-emit-index-url -o requirements.lock pyproject.toml
.venv/bin/pip-compile --strip-extras --no-emit-index-url --extra dev -o requirements-dev.lock pyproject.toml
```
