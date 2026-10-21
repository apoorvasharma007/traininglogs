# Architecture

One page for a reader with no memory of the project. Terms are from `docs/glossary.md`; the full
design, with reasons, is `docs/design.html`. Checked against `dev` on 2026-10-21.

## The pieces

One container on Google Cloud Run runs a FastAPI server. It serves the API and the built React app
at `/`. Data lives in Postgres on Supabase. People sign in with Supabase; the server checks the
sign-in pass on every request and never stores passwords.

| Folder | What it does |
|---|---|
| `frontend/src/screens/` | One file per screen: Train, Programs, Progress, History, Settings, Review (the confirmation card), Session (a live session). |
| `frontend/src/components/` | Shared UI pieces: `BottomBar`, `Sheet`, pickers, steppers. |
| `frontend/src/lib/` | API calls (`api.ts`), sign-in (`auth.ts`), the outbox that holds finished live sessions on the phone (`store.ts`). |
| `src/traininglogs/api/` | `app.py` has every endpoint. `auth.py` checks the sign-in pass and maps it to a user. `schemas.py` has request and response shapes. |
| `src/traininglogs/ingest/` | The three ways a session is made: `extract.py` (note to confirmation card), `confirm.py` (card to session), `manual.py` (live session to session). |
| `src/traininglogs/agent/` | The AI extraction: prompts, model providers (Anthropic; Groq for free evals), the checks, AI fixes (`patch.py`) and manual edits (`card_edits.py`). |
| `src/traininglogs/db/` | `schema.sql` (all 16 tables), `insert.py` and `fetch.py` (every function takes the owner), `programs.py`, `ids.py` (UUID v7). |
| `src/traininglogs/models/` | Pydantic models of a session as stored. |
| `src/traininglogs/analytics/` | Estimated max, personal records, the Progress view's data. |
| `src/traininglogs/export/`, `alerts.py` | Export as CSV or JSON; feedback posted to Discord. |
| `tests/` | pytest, against a real Postgres. `signed_in.py` makes test users A and B. |
| `scripts/` | Evals (`eval_arms.py`, `eval_ab.py`), the accounts migration, copying prod to a dev database. |
| `infra/` | Terraform for Google Cloud: a staging project and a prod project. |
| `.github/workflows/` | `ci.yml` checks every PR and push; `deploy.yml` ships `dev` to staging and `main` to prod, only when a push changes the app or its infrastructure. |

## How a note becomes a session

1. The Log from Notes screen sends the note: `POST /inputs`.
2. `ingest/extract.py` saves it as an input, then `agent/extraction.py` runs the AI extraction:
   one call splits the note into exercises, one reads the session header, then one call per
   exercise. Code checks the result against the note (`audit`). A failed exercise becomes a
   flagged placeholder; the rest keep their data.
3. The AI extraction is saved as a confirmation card (`input_text_confirmation_cards.extract`).
   Every model call is a row in `ai_call_logs`.
4. The Review screen shows the card (`GET /extractions/{id}`). An AI fix
   (`POST /extractions/{id}/correct`) returns edits that code applies; a manual edit
   (`POST /extractions/{id}/edit`) needs no AI.
5. Confirm (`POST /extractions/{id}/confirm`): `ingest/confirm.py` writes the session and its
   exercises, sets, session warm-up and cool-down.

## How a live session is saved

The Session screen keeps the session on the phone. At Finish it goes into the outbox (IndexedDB,
`frontend/src/lib/store.ts`), which sends it with `POST /sessions` when the server can be reached.
`ingest/manual.py` saves it with an input of kind `manual` and no confirmation card. A session the
server refuses is set apart so it doesn't hold back the others.

## Programs and progress

Programs, program workouts and following live in `db/programs.py`, behind `/programs` and
`/workouts`. Program templates are in code (`program_templates.py`). The Train tab starts the
followed program's next program workout with last time's weights (`GET /exercises/last`).
Progress reads sessions through `analytics/` (`/progress/lifts`).

## Where data lives and who sees it

- The schema is `src/traininglogs/db/schema.sql`. The tests apply it to the test database on every
  run. The server doesn't apply it: a change reaches staging and production only when someone runs
  it there by hand, following the production data rules in `CLAUDE.md`.
- Every table of people's data has `user_id`. A child row must have its parent's owner, which the
  database enforces with composite foreign keys. Row-level security is on, with no policies, so
  only the server's connection reads data.
- Production and staging each have their own Supabase database and Google Cloud project.
