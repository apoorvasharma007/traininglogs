---
name: verify
description: Check that a change works before it merges or after it deploys. Runs the Python suite on a private test database, the frontend checks CI runs, the local app on test data, and trying the change on staging after it deploys. Use before squashing a step, opening a PR, or after a deploy.
---

# Verify a change

This is how changes are checked today. It was built as the quickest way to a working app, and its
redesign is parked in `ai-workflow-plan.md`.

## 1. A private test database

The tests empty every table of people's data, so they run only on a database of their own. The
shared `traininglogs_test` on port 5433 can carry another branch's schema, so make one per branch:

```bash
docker compose up -d db_test
docker compose exec db_test createdb -U traininglogs traininglogs_<branch>   # once; "already exists" is fine
export TEST_DATABASE_URL=postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_<branch>
```

The tests apply `src/traininglogs/db/schema.sql` themselves, so a new database needs nothing else.

## 2. The Python suite

```bash
.venv/bin/pytest tests/
```

A step merges only with 0 failed and 0 skipped. Report the counts as they came out.

## 3. The frontend checks

The same four CI runs:

```bash
cd frontend && npm run typecheck && npm run lint && npm test && npm run build
```

## 4. An app change, in a browser

Build the app, then run it on the test database, never on `.env`'s `DATABASE_URL` (production):

```bash
cd frontend && npm run build && cd ..
DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/uvicorn traininglogs.api.app:app --reload
```

Open `http://localhost:8000/` and sign in. Your first request adds your user to the test database.
Live sessions and programs cost nothing. A confirmation card needs one AI extraction, a paid call of
a few cents: paste a note from `tests/fixtures/valid/`.

## 5. On staging, after the merge into `dev`

A merge into `dev` deploys staging. Open staging on your phone, sign in, and try the change the way
a user would. The URL is `terraform -chdir=infra/environments/staging/app output -raw service_url`.

Then check sign-in is still required: a request with no sign-in gets `401`.

```bash
curl -s -o /dev/null -w "%{http_code}\n" <staging URL>/sessions
```

After a release, do the same on production (https://traininglogs-875429444117.us-east1.run.app).
