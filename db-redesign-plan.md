# Database redesign for accounts

Part of phase 9 step 3 (`accounts`). Decided with Apoorva on 2026-10-06, designed for a million
users while serving ten.

## Goal

Every person's data is theirs alone, enforced by the database, not only by the server's code;
keys that never need changing as the app grows; and table names that say what they hold. Done
before anyone else has data, while production has 130 sessions and the change is cheap.

## Decisions

1. **Keys mean nothing.** Every table's `id` is a time-ordered UUID (version 7), made by our code
   (Postgres 17 can't). No id is built from data or chosen by the phone. Rules like "the same note
   twice" are unique constraints per user, not keys.
2. **The owner is on every table** except shared reference data. Each child points at its parent
   by `(user_id, parent_id)`, so the database refuses a child whose owner differs from its
   parent's, and refuses a link to another person's record. Every index on owned data leads with
   `user_id`. This is what lets the data be split by user later without a redesign.
3. **The app's own `users`**, mapped to the sign-in account by `auth_id`. The account is private;
   the public-facing part is `profiles`.
4. **Exercises have two levels.** `user_exercises` are a person's own, in their words, created
   automatically the first time a name is used. `exercises` is a shared, curated list (no owner)
   with equipment and muscles; a person's exercise may link to one, automatically when the name
   is obvious. Equipment lives only on the shared list, so people's naming is never boxed in.
5. **Row-level security** on every table, no policies, as now.
6. **Times:** every table has `created_at`, every changeable one `updated_at`. Sessions get
   `started_at` and `ended_at`. "Today" uses the person's timezone, not the server's.
7. **Order is `position`** everywhere (sessions used `number`).
8. **The API's JSON stays the same,** so the app doesn't change for this.
9. **Production is copied into staging** for testing, with each person's sign-in id remapped by
   email; staging is flushed and recopied as often as useful. Privacy of copies is revisited when
   there are more users.
10. **Confirmation cards are only for notes.** A note read by the AI becomes a card you fix and
    confirm. A session logged in the app is saved straight from its input, with no card (it used
    to make a draft and confirm it in the same instant). Every workout session links to the input
    it came from; a note's session also links to its card.
11. **The old "repeat" call is deleted** (`POST /sessions/{id}/repeat`, `ingest/repeat.py`). The
    app never calls it: "Do this again" builds the session on the phone.

## Tables

Every owned table also has `id uuid PRIMARY KEY`, `user_id uuid NOT NULL`, `UNIQUE (user_id, id)`
and `created_at`; they're left out below. → marks a link by `(user_id, …)`.

**`users`** (private account; owner of everything)
`id`, `auth_id uuid UNIQUE`, `email`, `status` (`active`, `disabled`), `role` (`member`,
`admin`), `timezone` (from the phone at first sign-in, e.g. `Asia/Kolkata`), `weight_unit`
(`kg`, `lb`), `ai_monthly_limit_usd` (default 1.00), `created_at`, `updated_at`, `last_seen_at`,
`deleted_at` (account deletion requested).

**`profiles`** (public-facing, one per user)
`user_id` (primary key, → users), `display_name`, `username` (unique, optional),
`avatar_url` (optional), `created_at`, `updated_at`.

**`input_text`** (what a person wrote or entered, exactly as given; was `raw_inputs`)
`content`, `kind` (`text`, `manual`; was `source_kind`), `client_id` (the phone's id for an app
session; `UNIQUE (user_id, client_id)`), `checksum`, `source` (was `source_file`; a repeat's
source session).

**`input_text_confirmation_cards`** (the AI's reading of a note, with your fixes, waiting for
Confirm; was `extractions`)
→ `input_id`, `model`, `prompt_version`, `extract`, `uncertain_fields`, `warnings`, `status`
(`pending`, `confirmed`, `rejected`), `corrections`, `confirmed_at`.

**`ai_call_logs`** (one paid AI call; was `llm_calls`)
→ `input_id`, `step`, `model`, `attempts`, `input_tokens`, `output_tokens`, `cost_usd`, `ms`,
`cached`, `failed`, `raw_payload`. Index `(user_id, created_at)` for the monthly cap.

**`workout_sessions`** (a saved session; was `sessions`)
`date`, `started_at`, `ended_at`, `duration_minutes`, `focus`, `notes`, `dedup_key` (date plus a
fingerprint of the text; `UNIQUE (user_id, dedup_key)`), → `input_id` (always: the note or the
app session's record), → `confirmation_card_id` (notes only; was `extraction_id`),
→ `program_workout_id`, plus the old columns the app still reads: `program`, `program_author`,
`program_length_weeks`, `phase`, `week`, `is_deload_week`, `weight_unit`, `source`.
`user_name` is dropped. Index `(user_id, date)`.

**`workout_session_exercises`** (an exercise in a session; was `exercises`)
→ `session_id`, `position`, → `user_exercise_id` (always set), `name` (as typed), `notes`,
`warmup_notes`, `goal_weight_kg`, `goal_sets`, `goal_rep_min`, `goal_rep_max`,
`goal_rest_seconds`, `goal_distance_meters`, `goal_target_duration_sec`, and the other old
columns as they are.

**`workout_session_sets`** (a set; `working_sets` and `warmup_sets` merged)
→ `exercise_id` (the session exercise), `position`, `kind` (`warmup`, `working`), `weight_kg`,
`reps_full`, `reps_partial`, `left_reps_full`, `left_reps_partial`, `right_reps_full`,
`right_reps_partial`, `rpe`, `rep_quality`, `rest_seconds`, `duration_seconds`,
`distance_meters`, `heart_rate_bpm`, `notes`, `failure_technique` (drop sets, myo-reps and the
like stay as detail on their set). A warm-up's `rep_count` becomes `reps_full`.

**`workout_session_warmups`** and **`workout_session_cooldowns`** (was `warmups`, `cooldowns`)
→ `session_id`, `position`, `name`, `reps`, `duration_seconds`, `notes`.

**`programs`** `name`, `deload_after_days`, `following` (one per user), `following_since`,
`archived_at`, `updated_at`.

**`program_workouts`** → `program_id`, `position`, `name`, `warmup`, `cooldown`, `archived_at`,
`updated_at`.

**`program_workout_exercises`** → `workout_id`, `position`, → `user_exercise_id`, `name`,
`warmup_sets`, `working_sets`, `target_reps`, `amrap`, `alternatives` (names, for now).

**`user_exercises`** (a person's own exercise)
`name` (`UNIQUE (user_id, lower(name))`), `exercise_id` (→ the shared list, optional),
`updated_at`.

**`exercises`** (shared, curated, no owner)
`id`, `name`, `equipment` (`barbell`, `dumbbell`, `kettlebell`, `band`, `cable`, `machine`,
`bodyweight`, `other`), `movement` (squat, hinge, push, pull…), `muscles`, `other_names`
(for automatic matching: "back squat", "bb squat", "squats"), `created_at`, `updated_at`.
Starts with about 30 basic lifts.

Dropped: `exercise_pins` (pinned notes were removed).

Also not carried over: two leftover columns production has but no schema file describes since an
early version, `exercises.exercise_type` and `working_sets.set_type`; every row holds the default
`'strength'` (checked 2026-10-06), so they carry nothing. Old sessions imported from the markdown
logs have no input; each gets one of kind `import`, holding the session as it was stored.

**Production's drafts in the migration** (checked 2026-10-06): the 13 AI readings of notes (9
confirmed, 4 rejected) become `input_text_confirmation_cards`. Not carried over: 1 draft from an
app session (its session keeps its link to its input) and 1 pending draft from the old repeat
call, which nothing can reach.

## Exercise names

- **Saving a name** finds the person's `user_exercises` entry with the same name, ignoring
  capitals and extra spaces, or creates one. A new one links to a shared exercise when its name
  matches one of that exercise's names.
- **Tidying a typed name** (step 4, in the app and on the server): trim, squash repeated spaces,
  capitalise every word (`Bench Press`, `45° Lateral Raise`). Words with capitals, numbers or
  symbols stay as typed. Only two abbreviations are written in capitals: `DB` and `BB`. More
  rules later.
- **Suggestions while typing** (step 4): the person's exercises and the shared list are kept on
  the phone (under 100 KB, refreshed when changed) and searched there, offline, in about a
  millisecond. Picking one links it; a new name is allowed, with a note to check it.
- **Improving the shared list** (step 4 and after): names people created that didn't link are
  counted (names only, never anyone's sessions), and reviewed, with an expert where useful, to
  add exercises or other names.

## Blast radius

- `src/traininglogs/db/schema.sql`: rewritten for the new tables.
- `db/insert.py`, `db/fetch.py`, `db/programs.py`: new names, owners passed down to every child.
- `ingest/` (capture, extract, confirm, manual, program_history), `api/app.py`, `api/auth.py`:
  new names; cards only for notes, client ids and dedup keys.
- Deleted: the repeat endpoint in `api/app.py`, `ingest/repeat.py`, and the repeat tests in
  `tests/test_repeat.py` and `tests/test_isolation.py`. The one test there about History's
  session list moves to `tests/test_api.py`.
- `analytics/progress.py`: reads `workout_session_sets` by `kind`.
- A new `src/traininglogs/db/ids.py`: uuid7.
- Tests: the database and API tests follow the new names; the isolation and account tests keep
  their checks.
- `scripts/copy_prod_to_dev.py`: the new tables, and sign-in ids remapped by email.
- A migration script for production's existing data.
- Docs: `docs/design.html` (data model), `CLAUDE.md`, `.claude/db-migration.md`, the changelog.

## Steps

All on `phase-9/next-3-accounts`, locally, nothing pushed until the whole of step 3 is ready.

- [x] 1. `ids.py` (uuid7) with tests.
- [x] 2. The new `schema.sql`: every table above, keys, links, indexes, row-level security, and a
      test per rule (owners match parents, links can't cross users, uniqueness per user).
- [x] 3. Saving and reading on the new tables (`db/`, `ingest/`), with exercises found or created
      on save; app sessions saved without a card; the repeat call deleted. The suite green.
- [x] 4. The API on the new tables; the isolation and account tests green.
- [x] 5. The migration script: from today's tables to the new ones, every row owned by one given
      user, new ids, links rebuilt, distinct exercise names made into that user's exercises.
      Tested on a copy of production in the local dev database, comparing counts and a sample of
      sessions before and after.
- [x] 6. The copy script on the new tables, remapping sign-in ids by email.
- [x] 7. The starter shared list (about 30 lifts) and automatic linking.
- [x] 8. Docs.
- Then the rest of step 3: Terraform (`SUPABASE_URL`, the API key removed), the app's sign-in
  screen (3.4, design first), the AI cap (3.5), daily backups (3.6), and the release: staging
  first, then production with a backup and approval.

## Later (saved, not now)

- **Supersets and circuits:** one optional `group_number` on session and program exercises;
  exercises sharing a number are done back to back in rounds (two is a superset, three or more a
  circuit; set N of each is round N). Screens and AI support designed separately.
- **More naming rules** beyond DB and BB.
- **Personal data for leaderboards** (birth year, sex, bodyweight over time, location), added only
  with the feature that needs it.
- **Dropping the markdown-era session columns** once nothing reads them.

## ▶ Resume here

2026-10-06: all 8 steps built and reviewed on `phase-9/next-3-accounts`, local only (nothing
pushed), last commit `c907062`. Server suite 718 passed, 96% line coverage; app suite 102 passed.
Rehearsed on a copy of production: every count and all 131 sessions identical.

Next, the rest of step 3: Terraform (`SUPABASE_URL` for each server, the API key and its secret
removed), the app's sign-in screen (3.4, design first; until it exists the app can't talk to this
server, so nothing deploys before it), the AI cap (3.5), daily backups (3.6), then the release:
staging first, then production with a backup and approval.
