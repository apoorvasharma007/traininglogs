# Phase 9 plan: fixes, staging, more users

## Goal

Get to a version five people can use, and later a few hundred. First the fixes from Apoorva's
first real use of 4.0.0, then a staging environment so changes can be tried on a phone without
touching production, then accounts so each person sees only their own data. After that, one name
per exercise per person, and an analytics page each person can arrange.

## Decisions so far

- Login is an email link (Supabase Auth). No passwords.
- One database for everyone; every row has an owner and the database enforces it. Not a database
  per user: at about 12 KB per session, the free 500 MB holds roughly 40,000 sessions.
- A program inspires; the session decides. Alternatives no longer take turns: Start uses the
  first exercise, and a small swap icon in the session lists the alternatives.
- No natural language to SQL. The analytics page is built from cards each person picks and
  orders; a free model may later map a question to a card, never to raw SQL.

## Steps

Base branch `phase-9/next` from `dev`; one sub-branch per step, `phase-9/next-N-<step>`, squashed
into the base when both suites are 0 failed and 0 skipped.

- [ ] 1. `fixes`
  - Home: drop "Do a different workout".
  - Workout name: the field starts as "Workout N" and is edited in place; adding a workout asks
    for its name.
  - Reps target: one field; empty means as many as you can.
  - Deleting an exercise from a program's workout asks first.
  - A set's note shows as a small marker on its row.
  - Alternatives: Start uses the first exercise; a swap icon (⇄) beside the name opens a drawer
    listing the alternatives; tapping one switches the session to it.
  - Put Bench press back in Starting Strength's workout 2 (prod, with approval).
- [ ] 2. `staging`: a second Supabase project and Cloud Run service through Terraform
  (`infra/environments/staging`); `dev` deploys to staging, `main` to production as today.
- [ ] 3. `accounts`: email-link login, an owner on every row, isolation tests, per-user fixes
  (session ids, the one followed program, pins), a cap on AI use, app and database in one region
  with the connection pooler, daily backups, installable app.
- [ ] 4. `exercise-names`: a "Your exercises" screen with likely duplicates (pg_trgm), merge into
  aliases, autocomplete wherever a name is typed.
- [ ] 5. `insights`: an analytics landing page of cards each person picks and orders.
- [ ] 6. `design`: a layout and visual pass, mockups first.

## ▶ Resume here

2026-10-04: plan written. Next: cut `phase-9/next-1-fixes` and build step 1.
