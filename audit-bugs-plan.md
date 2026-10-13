# Audit bug fixes plan

Goal: fix the real bugs from `audit-bugs.md` (found on `main` `2b47e0d`, re-checked against `dev`). Scripts the audit flagged (#5, #7, `eval_arms.py`) are out of scope: they are meant to be deleted. #1, #2 and the unverified candidates are deferred.

Blast radius: `frontend/src/lib/store.ts`, `frontend/src/screens/review/`, `frontend/src/screens/session/Session.tsx`, `src/traininglogs/agent/{extraction,providers}.py`, `src/traininglogs/api/app.py`, their tests, `CHANGELOG.md`.

Method: base branch `fix/audit-bugs` from `dev`; one sub-branch per step, squashed into the base with the full suite green. The base merges to `dev` only after step 5, with Apoorva's yes.

- [x] 1 `fix/audit-bugs-1-outbox`: #9 a 4xx-rejected session moves to its own key on the phone and later sessions still send; cap saved duration at 1440 min so the 24 h case never reaches the server
- [x] 2 `fix/audit-bugs-2-assemble`: #4 and #6 `assemble()` turns ValidationError and provider errors into placeholders
- [x] 3 `fix/audit-bugs-3-review-save`: #8 Confirm stuck on "Saving…", #10 double-blur loses a correction
- [ ] 4 `fix/audit-bugs-4-save-session`: #11 Save Session shows an error when the IndexedDB write fails
- [ ] 5 `fix/audit-bugs-5-request-422`: #3 bad `extract` body returns 422, not 500

## ▶ Resume here

Steps 1 to 3 squashed into `fix/audit-bugs`. Suites green: 739 pytest, 142 vitest (a full vitest run occasionally times out one UI test under load; it passes on rerun). Next: step 4 on `fix/audit-bugs-4-save-session`.

AuthenticationError is deliberately still raised raw: a bad key should be loud, not a placeholder on every exercise.

Run pytest against a private database, because the shared test database on port 5433 carries the exercise-library branches' schema:
`TEST_DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_fix .venv/bin/python -m pytest -q`
