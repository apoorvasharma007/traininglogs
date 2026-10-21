# traininglogs

Rules for working in this repo, for Apoorva and any coding agent. What the app is: `README.md`. How
it works: `docs/architecture.md` (one page) and `docs/design.html` (in full). The words to use:
`docs/glossary.md`. Where changes break things: `docs/risk-map.md`.

## Where to start

- `roadmap.md` is the forward plan. Start at its `▶ Resume here` section.
- A task that spans sessions gets its own plan file in the repo root with a `▶ Resume here`
  section, like `ai-workflow-plan.md`. Finished plans move to `archived/plans/`.
- Rules for one part of the code are in `.claude/rules/` and load when you open matching files.
- Skills: `/setup` (machine setup, running the app), `/verify` (checking a change), `/release`,
  `/traininglogs-agent` (unattended bug-fix runs).

## Money

- Before any paid model run, run it with `--dry-run` (`scripts/eval_arms.py --dry-run`): it lists
  every call and spends nothing. Why: a full regeneration once priced at $6.76 against $3.29 left.
- Quote costs from a dry run or from the `ai_call_logs` table, never from memory.

## Production data

- `DATABASE_URL` in `.env` is production. For local runs use `DATABASE_URL="$TEST_DATABASE_URL"`.
- **Never write to production without Apoorva's yes in this session.** Show the exact SQL first,
  back up to `backups/`, run it in one transaction, compare row counts before and after, roll back
  on any surprise. Why: a regeneration once ran against production without pausing for approval
  (`archived/plans/pre-online-plan.md`).
- Mark, don't delete: an AI extraction that shouldn't count becomes `status = 'rejected'`. Why:
  deleting an input also deletes its `ai_call_logs` rows (ON DELETE CASCADE), and with them the
  cost history.

## Secrets

- Secrets live in `.env` locally and in Secret Manager on Google Cloud. Never put one in a
  committed file, a log, a command's printed output or Terraform state. Why: the repo is public.
- Project IDs are fine to commit; billing account IDs and keys are not.

## Branches and deploys

- Cut a base branch from `dev` per piece of work (`<area>/<topic>`), and one sub-branch per step
  (`<area>/<topic>-N-<step>`). Why: git refuses `a/b` when `a` is already a branch.
- Squash a step into its base. Merge the base into `dev`, and `dev` into `main`, with merge
  commits. Why: squashing into `dev` or `main` splits their history from the branches.
- A step merges into its base only with the full suite green: 0 failed, 0 skipped. Why: CI checks
  PRs into `dev` and `main`, not a local squash into a base branch.
- A push to `dev` deploys staging once CI passes, with no approval, if it changes the app or its
  infrastructure (`src/`, `frontend/`, `infra/`, `Dockerfile`, `pyproject.toml`,
  `requirements.lock`, `.github/workflows/`). Docs-only pushes skip the deploy.
- Merging `dev` into `main` is a release: its deploy waits for Apoorva's approval in the `prod`
  GitHub environment. Steps are in `/release`.
- Commit messages: `<type>: <what changed>`, type one of `feat`, `fix`, `test`, `refactor`,
  `chore`, `docs`.

## Tests

- **`TEST_DATABASE_URL` must point at a local test database, never staging or production.** Why:
  the tests TRUNCATE every table of people's data (`clean_test_data` in `tests/signed_in.py`).
- On `dev`, use a private database, not the shared one on port 5433 (it carries another branch's
  schema). Setup is in `/verify`.
- A change that breaks a test fixes or rewrites that test in the same step. Never skip, delete or
  loosen a test to get green. Why: CI is the only witness for unattended work.
- Before a step merges, check the change on the real thing: the suite, and for an app change the
  local app in a browser. After the merge into `dev`, try the change on staging. Steps: `/verify`.

## Words and docs

- Use the terms in `docs/glossary.md` in docs, plans, issues, commits, PRs and new code. Why: one
  concept had up to five names, and an agent copies the last one it saw.
- A PR that makes a rule, skill or doc wrong fixes it in the same PR. Why: the context describes
  today's code, flaws included, and must move with it, not ahead of it.
- A new concept gets a glossary row in the same PR. A clash you notice goes in the PR description,
  not a silent rename.
- A PR that changes behaviour adds a line under `[Unreleased]` in `CHANGELOG.md`: Added, Changed,
  Fixed or Removed. Why: it's the record of each version; `/release` moves these entries under the
  new version number.
- If the flow, the data model, the API or the hosting changes, update `docs/architecture.md` and
  `docs/design.html` in the same PR.
- Run the `unslop` skill on prose before committing docs or opening a PR, and check each fact
  against the code before writing it.
