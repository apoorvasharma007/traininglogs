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
  - Put Bench press back in Starting Strength's workout 2 (prod, with approval). Done 2026-10-04.
  - View and edit modes for programs and workouts; the session collapses finished exercises.
  - A lighter set drawer; effort as Moderate / Hard / All out (RPE 7 / 8.5 / 10); no LAST column.
  - Warm-up ramps for weighted exercises; session warm-up and cool-down, programmable per workout.
  - App-wide text review (2026-10-04): plain errors with codes, Warm-up / Remove / Update program
    wording, program templates (`GET /templates`, `POST /templates/{id}/copy`), simpler home card,
    "Update the program?" matched by workout line, estimated max only from sets with an RPE, Done
    screen kept across restarts.
  - Prod at release: `program_workouts.warmup` and `.cooldown` columns (approval first).
- [x] 2. `staging` (2026-10-05): Supabase project `traininglogs-staging` (ap-northeast-2, the
  free plan's region) and Google Cloud project `project-ff63b6ae-c18e-4350-961`, through Terraform
  in `infra/environments/staging`. Server in us-east1 like prod, so outbound data stays free.
  `dev` deploys to staging with no approval; `main` to prod with approval. Row-level security on
  every table in both databases, no policies (blocks Supabase's automatic API).
- [ ] 3. `accounts`: email-link login, an owner on every row, isolation tests, per-user fixes
  (session ids, the one followed program, pins, key lifts chosen per person), a cap on AI use, app and database in one region
  with the connection pooler, daily backups, installable app.
- [ ] 3b. `maxes`: a 1RM per lift, entered by a new user or taken from the estimated max in their
  history; warm-ups and working weights suggested from it, and plans that say "5 x 5 at 75%".
- [ ] 4. `exercise-names`: a "Your exercises" screen with likely duplicates (pg_trgm), merge into
  aliases, autocomplete wherever a name is typed.
- [ ] 5. `insights`: an analytics landing page of cards each person picks and orders.
- [ ] 6. `design`: a layout and visual pass, mockups first.

## Ideas for later

Not scheduled. Each needs accounts first, and its own design review.

- **Leaderboards.** Top lifters by age range, gender and region, opt-in only. Records need some
  check before they count (a video, or a judge), or the board fills with typos and fakes.
- **Community contests.** Time-boxed and local: "heaviest bench press in Bangalore this month",
  "biggest strength gain in 8 weeks". Prizes for winners. Same opt-in and checking as above.
- **Training by sport.** A database of the body's regions and abilities (strength, power, mobility,
  endurance, reflexes), each mapped to the exercises that train it and to the sports that need it,
  so someone can see what to train to move like a sprinter, a climber or a fighter.
- **AI-assisted program creation.** Describe what you want ("3 days a week, strength, home gym with
  a barbell"); the model drafts a program, you edit it before it's saved. A few cents per draft,
  behind the AI spending cap.
- **Community programs: share, then sell.** People publish programs others can copy and run, then
  sell them. Needs publishing and copying, moderation for junk and copied programs, and payments
  (Razorpay or similar, GST, refunds, payouts). Builds on the built-in program templates.

Rule for adding AI anywhere: use it where free text has to become structured data, or where the
person asks for it once and reviews the result. Never inside a session, which has to work offline,
instantly and for free; never where a simple rule is reliable.

## ▶ Resume here

2026-10-04: step 1 (`fixes`), including the app-wide text review, is built on
`phase-9/next-1-fixes` (last commit: the Done screen kept across restarts) and running on Apoorva's
test server (`uvicorn ... --host 0.0.0.0 --port 8010` on the dev copy; phone at
http://<laptop>:8010). Not released. Next: Apoorva tests on the phone; then, on "release", merge to
`phase-9/next` and `dev`, PR to `main`, apply the program_workouts columns to prod with approval,
approve CD. Open questions: move the offline / installable app earlier; drag to reorder exercises
in a session (needs a design).
