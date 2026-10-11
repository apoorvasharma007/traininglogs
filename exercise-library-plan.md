# Exercise library plan

Every exercise someone logs should mean one thing. Today a name is matched only ignoring case and
spaces, so "Weighted pull up" and "Weighted Pull ups" are two exercises, and nothing knows that a
cable fly works the chest. A shared library fixes that: each exercise has its muscles, joint actions,
movement pattern and equipment, people pick from it while logging, and their own exercises carry a
primary muscle too. Progress, Key Lifts, history prefill, and later leaderboards, community and
recovery tracking all read from the library instead of from typed names. With little data today
(one person's 107 names in the local copy; prod has a few more people), now is the cheapest time.

## What exists today

- `exercises`: a shared list of 32 (`schema.sql`), with equipment, one `movement` word, a muscle
  list (no primary or secondary) and `other_names` for automatic linking.
- `user_exercises`: each person's names, made the first time a name is used, linked to a shared
  exercise when the name matches one of its names (`db/insert.py`, `user_exercise_ids`). In the
  local copy 23 of 107 are linked.
- Nothing reads the link yet. Progress, Key Lifts (`analytics/key_lifts.py`), History,
  `GET /exercises/last` and `GET /exercises/{name}/history` all match by typed name.
- `db-redesign-plan.md` already planned the next part (suggestions while typing, kept on the
  phone; growing the shared list from names that don't link). This plan carries it out.

## Design (each part needs Apoorva's approval before it's built)

### 1. What an exercise records

| Field | Values |
|---|---|
| name | "Barbell Bench Press" |
| other names | how people write it: "bench", "bench press", "bb bench" |
| equipment | barbell, dumbbell, kettlebell, cable, machine, smith machine, band, bodyweight, other |
| primary muscle | exactly one, from the muscle list |
| secondary muscles | any number, from the muscle list |
| joint actions | from the joint action list, e.g. shoulder horizontal adduction, elbow extension |
| pattern | from the pattern list, e.g. horizontal push |
| measure | weight and reps, bodyweight reps, time, or distance (decides what Progress shows) |

### 2. The fixed lists (proposed, to approve item by item)

**Muscles (23):** chest; front delts, side delts, rear delts, rotator cuff; lats, upper back,
traps, lower back; biceps, triceps, forearm flexors, forearm extensors; abs, obliques; glutes,
hip flexors, adductors, abductors, quads, hamstrings, calves, tibialis; neck.

**Joint actions (standard anatomy):**
- shoulder: flexion, extension, abduction, adduction, horizontal abduction, horizontal adduction,
  internal rotation, external rotation
- shoulder blade: elevation, depression, protraction, retraction
- elbow: flexion, extension; forearm: pronation, supination
- wrist: flexion, extension, radial deviation, ulnar deviation
- spine: flexion, extension, side bending, rotation
- hip: flexion, extension, abduction, adduction, internal rotation, external rotation
- knee: flexion, extension
- ankle: dorsiflexion, plantarflexion; foot: inversion, eversion
- neck: flexion, extension, side bending, rotation

**Patterns (10):** squat, hinge, lunge, horizontal push, vertical push, horizontal pull,
vertical pull, carry, rotation and anti-rotation, isolation.

### 3. Variations

Open decision. Either grip, stance, arm and angle variations are their own exercises ("Neutral
Grip Lat Pulldown"), as Hevy does, or one exercise with a variation picked when logging. Proposal:
own exercises, linked to a parent ("Lat Pulldown"), so Progress can show the family together or
apart.

### 4. Where the library comes from

free-exercise-db (public domain, about 800 exercises, 17 muscles, push/pull, compound/isolation,
equipment) as the starting data. A script maps it onto our lists; the result is a reviewed file in
the repo, and only exercises worth keeping go in (about 150 to 200 to start). Apoorva reviews the
list. Nothing is fetched at runtime.

### 5. A person's own exercises

Allowed, for anything the library lacks. Creating one asks for the primary muscle (required) and
equipment; the rest is optional. Own exercises count in Progress and recovery like library ones.
Names people create are reviewed from time to time and added to the library.

### 6. Logging

The exercise name box becomes a search over the library and the person's own exercises, kept on
the phone so it works offline (the plan from `db-redesign-plan.md`). Picking one fills last time's
sets in grey (history prefill). Not found: "Add Your Own". The picker's look is a visual change:
mockup first, approved before it's built.

### 7. Existing logs

Every `user_exercises` entry gets linked to a library exercise (or becomes an own exercise with a
primary muscle). A mapping file lists each name and its match; Apoorva reviews it. Stored names are
never changed, only links. Run as a dry run on a copy of prod first, then on prod in one
transaction with a backup and same-session approval.

### 8. Reading by exercise, not by name

Progress, Key Lifts, History and the prefill read through the link. Key Lifts become library
exercises. The exercise endpoints move to ids, and the old ones stay working until phones with the
old app have updated:

| Today | New |
|---|---|
| `GET /exercises/last?name=` | `GET /exercises/recent?id=` |
| `GET /exercises/{name}/history` | `GET /exercises/{id}/history` |
| none | `GET /exercises` (the library and your own, for the phone) |
| none | `POST /exercises` (add your own) |
| `GET /progress/lifts`, `PUT /me/key-lifts` | Key Lifts read and saved under one path |

## Blast radius

- Server: `db/schema.sql` (exercise fields, the lists), `db/insert.py`, `db/fetch.py`,
  `db/programs.py`, `analytics/key_lifts.py`, `analytics/progress.py`, `api/app.py`,
  `api/schemas.py`, a new library data file and its loader, a mapping script in `scripts/`
- App: the name box in `screens/session/ExerciseCard.tsx`, `screens/WorkoutPlan.tsx`,
  `screens/review/Review.tsx`; a picker component; `lib/store.ts` (library on the phone);
  Progress and Key Lifts screens
- Prod database: one migration (new columns) and one linking run, both approved in session
- Docs: `docs/design.html`, `CHANGELOG.md`, `README.md` if the flow changes

## Steps

Base branch `exercises/library` from `dev`, a sub-branch per step (`exercises/library-N-<step>`),
squashed into the base; the base merges into `dev` when every step is done and the suite is green.

- [ ] 1. Design approval: fields, the three lists, variations (sections 1 to 3).
- [ ] 2. Library data: script from free-exercise-db, reviewed list of 150 to 200.
- [ ] 3. Schema and loading: new fields, the lists as checks, library loaded; tests.
- [ ] 4. Own exercises: `POST /exercises` with a required primary muscle; tests.
- [ ] 5. Linking existing logs: mapping file reviewed, dry run on a prod copy, prod run approved.
- [ ] 6. Reads by exercise: Progress, Key Lifts, History, new endpoints, old ones kept; tests.
- [ ] 7. Picker: mockup approved, then built, with history prefill on pick; tests, checked on
      the phone.
- [ ] 8. Effort fix (can go any time): checking a set doesn't ask for effort when it has one.
- [ ] 9. Release.

Then the guide (`guide-plan.md`): clips recorded on the new picker.

## ▶ Resume here

2026-10-11: plan written and committed on `exercises/library` (from dev at `d5481a4`, local
only, not pushed). Nothing built.

Next: Apoorva reviews sections 1 to 3 (fields, the three lists, variations), item by item; the
muscle list first. Then step 2.

Context for the next session:
- Prod runs 5.0.0 (released 2026-10-11). The local data copy (`traininglogs_dev`, port 5433) has
  107 exercise names for one person, 23 linked; prod has a few more people.
- The Title Case change (program templates now "Bench Press", "Upper / Lower") is on `docs/guide`,
  not on dev yet. If this branch touches `program_templates.py`, merge `docs/guide` first or
  expect a conflict.
- The effort fix (step 8) is a one-line change in `screens/session/Session.tsx` `tick()`: ask
  for effort only when `set.rpe == null`, plus a test.
- The guide waits for this plan (`guide-plan.md`).
