# traininglogs

The working rules for this repo, for Apoorva and for any coding agent. What the app is lives in
[`README.md`](README.md); how it works lives in [`docs/design.html`](docs/design.html). Link to
them instead of repeating them here.

## Where to start

[`roadmap.md`](roadmap.md) is the forward plan. Start at its `▶ Resume here` section: it has the
current state and what's safe to run. A task that spans sessions gets its own plan file in the
repo root with a `▶ Resume here` section of its own, like `docs-overhaul-plan.md`. Finished and
superseded plans move to [`archived/plans/`](archived/plans/).

## Rules that cost money or data

Paid model calls:

- Never start a paid run without a dry run first. `scripts/eval_arms.py --dry-run` lists every
  call it would make and spends nothing.
- A prompt or schema change re-keys the eval cache, so batch prompt changes into one
  measurement.
- Quote costs from a dry run or from `llm_calls`, never from memory.

The production database (Supabase, `DATABASE_URL`):

- Anything that writes to it needs Apoorva's approval in the same session. Approval from an
  earlier session doesn't carry over.
- Show the exact statements first. Run them in one transaction, in the foreground, check row
  counts before and after, and roll back on any surprise.
- Take a backup before changing many rows; `backups/` is git-ignored for this.
- Prefer marking over deleting. An extraction that shouldn't count becomes `rejected`; deleting a
  raw input also deletes its `llm_calls` cost history.

Secrets:

- They live in `.env` locally and in Secret Manager on Google Cloud. Never in a committed file, a
  log, a command's printed output or Terraform state.
- The repo is public. Project IDs are fine to commit; billing account IDs and keys are not.

## Local development

```bash
python -m venv .venv
.venv/bin/pip install -e .
cp .env.example .env              # then fill it in, see below
docker compose up -d db_test      # Postgres for the tests, on port 5433
```

| `.env` variable | Needed for | |
|---|---|---|
| `DATABASE_URL` | the app | Required. Points at production; see the warning below. |
| `API_KEY` | the app | Required. The app won't start without it. |
| `ANTHROPIC_API_KEY` | extraction and typed corrections | Required |
| `ANTHROPIC_WORKSPACE_ID` | Anthropic keys not scoped to a workspace (`sk-ant-usr…`) | Required with such a key |
| `TEST_DATABASE_URL` | the tests | Defaults to the Docker database on port 5433 |
| `GROQ_API_KEY` | `eval_ab.py` comparing models | Optional |
| `ALLOWED_ORIGINS` | calling the API from a page on another origin | Optional; the app's own page doesn't need it |

`LOCAL_DATABASE_URL` and `REGEN_DATABASE_URL` in `.env.example` belong to the retired markdown
flow; nothing in the app reads them.

Run the app. It serves the API and the web UI from one process at `http://localhost:8000/`:

```bash
DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/uvicorn traininglogs.api.app:app --reload
```

Point `DATABASE_URL` at the test database like this when trying things out. Without it, the app
reads and writes production. Each Extract is a paid model call either way.

To try things on real data without touching production, copy it into a local dev database (this
only reads production) and run the app on port 8010 against the copy:

```bash
.venv/bin/python scripts/copy_prod_to_dev.py
DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_dev \
    .venv/bin/uvicorn traininglogs.api.app:app --port 8010
```

Run the tests:

```bash
.venv/bin/pytest tests/
```

## Branching and releases

```
main   what's deployed; only dev merges into it
 └── dev   integration branch
      └── <area>/<topic>                 a base branch per piece of work: phase-6/deploy, docs/overhaul
           └── <area>/<topic>-N-<step>   one sub-branch per step
```

- Cut the base branch from `dev`, and one sub-branch per step. Name sub-branches with `-N-<step>`,
  not `/<step>`: git refuses a branch named like a directory under another branch.
- Squash each finished step into its base. Merge the base into `dev`, and `dev` into `main`,
  with merge commits. Never squash into `dev` or `main`; that splits their history.
- A step merges only with the full suite green: 0 failed, 0 skipped.
- A release is merging `dev` into `main`. CI runs, then CD waits for Apoorva's approval in the
  `prod` GitHub environment, applies the app's Terraform and deploys. To publish a version, bump
  `pyproject.toml`'s `version` and move the changelog's `[Unreleased]` entries under the new
  version first; CI then tags it and creates the GitHub release.
- Commit messages: `<type>: <what changed>`, with types `feat`, `fix`, `test`, `refactor`,
  `chore`, `docs`.

## Testing

- Tests that touch the database use the real test database in Docker, never mocks.
- A change that breaks tests gets its tests fixed or rewritten in the same step. Don't skip or
  delete a test to get green.
- New models get tests for valid construction, each validator's accept and reject cases, and a
  `model_dump(mode="json")` round trip.
- A web UI change gets checked in a browser against the local app before it merges.
- After a deploy, open the live app and check that the page loads and a request without the API
  key gets `401`.

## Docs

- Every pull request that changes behaviour adds a line under `[Unreleased]` in
  `CHANGELOG.md`: Added, Changed, Fixed or Removed.
- If the flow, the data model, the API or how it's hosted changes, update `docs/design.html` in
  the same pull request and its date at the top and bottom. Never edit the version inside
  `<span class="app-version">`; CI sets it on merge to `main`.
- Write every document in plain language. No em dashes, no filler, active voice, sentence-case
  headings. Say what something does or give the number, not how it feels. Check facts against the
  code before writing them down.
- `docs/index.html` is the old static dashboard, rebuilt only by the retired command-line flow.
  Don't edit it by hand.

## Working conventions

- Python 3.10 or newer, PEP 8, type hints on every function.
- Solve the problem in front of you. No abstractions for futures that haven't arrived, and no ORM.
- Don't rename database columns or Pydantic fields without being asked; the API, the UI and the
  stored data depend on them.
- Infrastructure changes go through Terraform in `infra/`, never by hand in the console. See
  [`infra/README.md`](infra/README.md).

## Guides

| Guide | Read it before |
|---|---|
| [`infra/README.md`](infra/README.md) | Changing anything on Google Cloud |
| [`.claude/db-migration.md`](.claude/db-migration.md) | Changing what the database stores |
| [`.claude/testing-guide.md`](.claude/testing-guide.md) | Testing a change, locally or after a deploy |

Guides for finished work and retired tools are in [`archived/guides/`](archived/guides/).
