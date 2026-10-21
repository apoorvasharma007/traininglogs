# Audit bug fixes plan

Goal: fix the real bugs from `audit-bugs.md` (found on `main` `2b47e0d`, re-checked against `dev`). Scripts the audit flagged (#5, #7, `eval_arms.py`) are out of scope: they are meant to be deleted. #1, #2 and the unverified candidates are deferred.

Blast radius: `frontend/src/lib/store.ts`, `frontend/src/screens/review/`, `frontend/src/screens/session/Session.tsx`, `src/traininglogs/agent/{extraction,providers}.py`, `src/traininglogs/api/app.py`, their tests, `CHANGELOG.md`.

Method: base branch `fix/audit-bugs` from `dev`; one sub-branch per step, squashed into the base with the full suite green. The base merges to `dev` only after step 5, with Apoorva's yes.

- [x] 1 `fix/audit-bugs-1-outbox`: #9 a 4xx-rejected session moves to its own key on the phone and later sessions still send; cap saved duration at 1440 min so the 24 h case never reaches the server
- [x] 2 `fix/audit-bugs-2-assemble`: #4 and #6 `assemble()` turns ValidationError and provider errors into placeholders
- [x] 3 `fix/audit-bugs-3-review-save`: #8 Confirm stuck on "Saving…", #10 double-blur loses a correction
- [x] 4 `fix/audit-bugs-4-save-session`: #11 Save Session shows an error when the IndexedDB write fails
- [x] 5 `fix/audit-bugs-5-request-422`: #3 bad `extract` body returns 422, not 500

## ▶ Resume here

Complete. All five steps merged into `dev` and pushed on 2026-10-13 (742 pytest and 143 vitest at the time). Open items live in `audit-bugs.md`.
