# Bug audit of main (2026-10-13)

Found by a dynamic workflow (finders, then two skeptics per finding who tried to refute it). Audited commit: `main` at `2b47e0d`. Line numbers are from that commit and may differ on other branches. Findings were verified by reading code; nobody ran a failing request or test.

Scope audited: `src/traininglogs/` (api, db, agent, models), `scripts/`, `frontend/src/` (tests used as context only). Not audited: `tests/`, `docs/`.

Cost of the audit: 27 agents, about 1.33M subagent tokens (step 1 314k, step 2 493k, step 3 525k).

## Verified bugs (both skeptics failed to refute)

| # | Sev | Where | Bug |
|---|---|---|---|
| 1 | 4 | `src/traininglogs/api/auth.py:53` | `user_for` never reads `users.status`, so a disabled user with a valid token keeps full access. `users.ai_monthly_limit_usd` (`schema.sql:29`) is also never enforced. May be an unbuilt feature, not a regression. |
| 2 | 3 | `src/traininglogs/api/app.py:75` | DB pool is capped at `maxconn=10`. More than 10 concurrent requests raise `PoolError`, which nothing catches, so the client gets a 500 instead of the intended 503. Low likelihood for one user. Relies on psycopg2 behaviour from memory. |
| 3 | 3 | `src/traininglogs/api/app.py:340`, `:370`, `:412` | `TrainingLogLLMExtract.model_validate(body.extract)` on client data is not wrapped. A body like `{"extract": {}}` gives a 500, not a 422. |
| 4 | 4 | `src/traininglogs/agent/extraction.py:394` | `assemble()` catches only `LLMParserError` around `to_exercise()`. Values like `rpe=11`, `weight_kg=-5`, `duration_seconds=0` pass the provider check, then raise pydantic `ValidationError` and abort the whole extraction, discarding exercises already extracted. |
| 5 | 4 | `scripts/add_starting_strength.py:95` | Targets the pre-accounts schema. `create_program(conn, NAME)` has no `user_id` (TypeError), and queries use tables that no longer exist (`sessions`, `warmup_sets`). Dead against current main. |
| 6 | 3 | `src/traininglogs/agent/providers.py:315` (Anthropic), `:466` (Groq) | Only `RateLimitError` and `BadRequestError` are caught. After the SDK's built-in retries run out, timeouts, 5xx, overloaded and `AuthenticationError` escape as raw SDK exceptions and kill the whole run. |
| 7 | 3 | `scripts/correction_stats.py:22` | Queries an `extractions` table that `schema.sql` no longer has. The replacement is `input_text_confirmation_cards`. |
| 8 | 4 | `frontend/src/screens/review/Review.tsx:128` | If the focus-name edit fails, `if (!named) return` skips `setSaving(false)`. Confirm stays disabled and reads "Saving…" until the user leaves the screen. |
| 9 | 4 | `frontend/src/lib/store.ts:71` | `flush()` stops at the first error. A request the server rejects with a 4xx stays at the head of the outbox forever and no later session is sent. Reachable when a live session is open more than 24 hours (`ManualSessionIn` has `le=1440`) or reps exceed 1000. The empty-exercises case is already guarded; the "8.5 reps" case is mostly unreachable on phones. |
| 10 | 3 | `frontend/src/screens/review/useReviewDoc.ts:54` | `run()` has no in-flight guard. Two quick blurs send two requests from the same pre-edit extract; the second reply overwrites the first and one correction is lost. |
| 11 | 3 | `frontend/src/screens/session/Session.tsx:150` | `enqueue(request).then(...)` has no catch. If the IndexedDB write fails, Save Session appears to do nothing: sheet stays open, no error shown. |

Shared root cause: 4 and 6 are both "assemble() promises a failing worker becomes a placeholder, but only one exception type is handled". One fix there may cover both.

## Unverified candidates (found but not checked)

The per-step cap of 4 verified findings dropped these. Treat them as leads, not confirmed bugs.

| Sev | Where | Candidate |
|---|---|---|
| 3 | `frontend/src/lib/store.ts:57` | Outbox flush can skip or drop a session finished while a flush is running. Related to #9, worth checking first. |
| 3 | `frontend/src/lib/auth.ts:158` | Any failed token renewal signs the user out, including on temporary server errors. |
| 2 | `src/traininglogs/agent/validation_card_builder.py:163` | Uncertain-field names from the LLM do not match the card's field names, so uncertainty marks are silently lost. |
| 2 | `src/traininglogs/agent/schemas.py:304` | Failure technique text is dropped without trace when compact notation matches but parsing fails. |
| 2 | `src/traininglogs/agent/schemas.py:344` | Unilateral warmup reps are silently discarded with no warning. |
| 2 | `scripts/eval_arms.py:247` | `--files` crashes with `KeyError` for any file lacking ground truth. |
| 1 | `src/traininglogs/agent/patch.py:61` | `apply_edits` `int()` can raise `ValueError` on malformed list index steps. |
| unrated | `src/traininglogs/api/app.py:510` | Whitespace-only program name is saved as an empty string. |
| unrated | `src/traininglogs/api/app.py:149` | CORS `allow_methods` omits PUT, PATCH and DELETE. |
| unrated | `src/traininglogs/api/app.py:170` | Invalid `from_date` / `to_date` cause a database error and a 500. |

## ▶ Resume here

2026-10-13: fixed and merged into `dev` (pushed): #3, #4, #6, #8, #9, #10, #11. The plan is `archived/plans/audit-bugs-plan.md`. Skipped on purpose: #5, #7 and the `eval_arms.py` candidate (scripts meant to be deleted). Still open: #1 (disabled users keep access, may be an unbuilt feature), #2 (pool of 10 connections), and every candidate in the unverified table above. Next action if wanted: verify the unverified table, starting with `store.ts:57` and `auth.ts:158`, against `dev`.
