# Risk map

Where a change is most likely to break something, worst first. An agent takes extra care here, and
Apoorva reviews these areas hardest. Built from what was already known (`audit-bugs.md`, the
2026-10-21 context audit, one suite run), not a new audit. Checked against `dev` at `8c9b454` on
2026-10-21.

Test baseline that day: Python 748 passed, 0 failed, 0 skipped, 96% line coverage. Frontend 144
tests in 14 files, for about 45 screen and component files.

| # | Risk | Why it matters | Evidence | Until it's fixed |
|---|---|---|---|---|
| 1 | CI on `dev` has failed since 2026-10-13 | The rulesets need green CI, so nothing merges into `dev`. The audit fixes never reached staging. | All 144 frontend tests pass, but an unhandled `QuotaExceededError` thrown by `frontend/src/screens/session/session.test.tsx:161` fails the run. | Fix first. Every PR into `dev` is red until then. |
| 2 | Schema changes reach staging and prod only by hand | Code that needs a new column deploys fine and then fails on the missing column. | The server doesn't apply `schema.sql`. Four columns once went missing in prod (`.claude/rules/schema.md`). | Agents park schema work. A schema PR says what to run on each database. |
| 3 | Disabled users keep access, and AI spend has no limit | Anyone with an account can run paid AI calls without a cap. | `users.status` and `users.ai_monthly_limit_usd` are never read (`audit-bugs.md` #1, `api/auth.py`). | Keep sign-up closed in Supabase. |
| 4 | Phone outbox and sign-in | A lost finished session is lost training data. No server test can see it. | Unverified leads: `frontend/src/lib/store.ts:57` (a flush may drop a session finished during it), `frontend/src/lib/auth.ts:158` (any failed renewal signs out). | Reproduce with a test before changing either file. |
| 5 | Frontend tests are flaky on a busy machine | A red local run may be timing, not a bug. | Two local runs on 2026-10-21 failed different tests, each "unable to find" text, in `lift`, `programs`, `settings`, `signin` and `Review` tests. CI passed all 144. | Read the failure before believing it. Re-run once. |
| 6 | AI extraction quality isn't checked by CI | A prompt change can make extraction worse with every test green. | Tests mock the model provider. Quality is measured by paid evals (`scripts/eval_arms.py`). | Agents park prompt changes (`.claude/rules/prompts.md`). |
| 7 | API errors that return 500 instead of a clear error | One user sees a crash. | Pool of 10 connections raises an uncaught `PoolError` (`audit-bugs.md` #2). Leads: invalid `from_date`/`to_date` and a whitespace-only program name in `api/app.py`. | Reproduce with a test first. |
| 8 | Leftover API key config | Dead config that looks live confuses agents and readers. | `API_KEY` in `.github/workflows/ci.yml:31` and `infra/modules/app/cloud_run.tf:89`, with an `api-key` secret. The tf comment says a release removes it. | Remove in a planned infra change, not by an agent. |
| 9 | Docs that describe the old app | Agents and readers act on stale facts. | `README.md` and `docs/design.html` still describe an API key and one user. | Fix with the `design.html` section-by-section pass. |
| 10 | Local Python differs from CI | Code can pass locally and fail in CI. | The local `.venv` runs 3.13.7; CI, the Dockerfile and `.python-version` use 3.12. | Rebuild `.venv` with 3.12 (`/setup`). |
| 11 | Dead and stale code | Agents may "fix" code nothing runs. | `scripts/add_starting_strength.py` and `scripts/correction_stats.py` target tables that no longer exist (`audit-bugs.md` #5, #7). `analytics/corrections.py` names a gone table in its docstring. `parser/parse.py` is 53% covered. | Delete in a cleanup PR. |
| 12 | No Python linter or type checker | Style and type rules are advice only. | CI runs pytest only; the frontend has `oxlint` and `tsc`. | Parked: ruff and mypy in CI. |
