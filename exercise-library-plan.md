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

### 1. What an exercise records (approved 2026-10-11)

| Field | How many | Required | Values |
|---|---|---|---|
| Name | one | yes | "Bench Press (Barbell)" |
| Other names | any number | no | how people write it: "bench", "bb bench"; used for automatic linking only |
| Equipment | one | yes | barbell, ez bar, dumbbell, kettlebell, cable, machine, smith machine, band, bodyweight, other |
| Measures | one or more | yes | weight, reps, time, distance |
| Type | one | no | Compound, Isolation |
| Primary muscles | one or more | yes | from the muscle list; each counts 1 set |
| Secondary muscles | any number | no | from the muscle list; each counts 0.5 sets |
| Joint actions | any number | no | from the joint action list, e.g. hip extension, knee extension |
| Patterns | any number | no | from the pattern list; isolation exercises have none |

Library exercises have every field filled; a person's own exercises may leave the optional ones
empty.

**Measures** are which of the set's existing columns (`weight_kg`, reps, `duration_seconds`,
`distance_meters`) the exercise uses: bench press is weight and reps, a weighted plank weight and
time, a farmer carry weight and distance, a run distance and time. The set row shows those boxes
by default; any box can still be filled. Progress picks a headline number per combination
(heaviest set or estimated 1RM, most reps, longest hold, heaviest load over the distance, pace);
the exact rule is decided in step 6.

**Counting sets per muscle:** a set counts 1 for each primary muscle and 0.5 for each secondary
muscle, worked out when read, never stored. 3 sets of bench press give the chest 3 and the
triceps 1.5. This is the "fractional" method that fit best in Pelland et al. 2024 (meta-regression
of 67 studies). Weekly sets per muscle and recovery tracking read these totals.

### 2. The fixed lists (approved 2026-10-11)

**Muscles (approved 2026-10-11): 17 groups, 36 muscles.** An exercise's primary and secondary
muscles are muscles; Progress and recovery total them by group. Checked against anatomy
references (StatPearls, Kenhub, TeachMeAnatomy) and EMG studies.

| Group | Muscles |
|---|---|
| Chest | Upper Chest, Mid/Lower Chest |
| Shoulders | Front Delts, Side Delts, Rear Delts, Rotator Cuff |
| Serratus | Serratus |
| Lats | Lats |
| Upper Back | Upper Traps, Mid Traps, Lower Traps, Rhomboids |
| Lower Back | Spinal Erectors, Quadratus Lumborum |
| Biceps | Biceps, Brachialis |
| Triceps | Triceps Long Head, Triceps Lateral/Medial Heads |
| Forearms | Brachioradialis, Forearm Flexors, Forearm Extensors |
| Core | Abs, Obliques, Transverse Abdominis |
| Glutes | Glute Max |
| Hips | Abductors, Adductors, Hip Flexors |
| Quads | Rectus Femoris, Vastus Muscles |
| Hamstrings | Hamstrings |
| Calves | Gastrocnemius, Soleus |
| Shins | Tibialis |
| Neck | Neck Flexors, Neck Extensors |

What each one covers, where it isn't obvious:
- Upper Chest is the clavicular head; Mid/Lower Chest is the sternocostal head (most of the
  muscle) and the small abdominal part.
- Lats include teres major. Rotator Cuff is supraspinatus, infraspinatus, teres minor and
  subscapularis.
- Upper Traps also extend the neck; they stay under Upper Back.
- Brachialis isn't part of the biceps; the group keeps the name people search for.
- Brachioradialis is a forearm muscle that bends the elbow (hammer and reverse curls).
- Glute Max only; Abductors are glute med, glute min and TFL. Hip Flexors are iliopsoas and
  sartorius; rectus femoris counts under Quads.
- Triceps Long Head and Rectus Femoris are split out because they cross a second joint
  (shoulder, hip).
- Neck Flexors: sternocleidomastoid. Neck Extensors: splenius and the deep neck extensors.

**Joint actions (approved 2026-10-11): 11 joints, 44 actions.** Plain name, anatomical joint in
brackets.

| Joint | Actions |
|---|---|
| Shoulder (glenohumeral) | flexion, extension, abduction, adduction, horizontal abduction, horizontal adduction, internal rotation, external rotation |
| Shoulder blade (scapulothoracic) | elevation, depression, protraction, retraction, upward rotation, downward rotation |
| Elbow | flexion, extension |
| Forearm (radioulnar) | pronation, supination |
| Wrist | flexion, extension, radial deviation, ulnar deviation |
| Trunk (thoracic and lumbar spine) | flexion, extension, lateral flexion, rotation |
| Neck (cervical spine) | flexion, extension, lateral flexion, rotation |
| Hip | flexion, extension, abduction, adduction, internal rotation, external rotation |
| Knee | flexion, extension, internal rotation, external rotation |
| Ankle (talocrural) | dorsiflexion, plantarflexion |
| Foot (subtalar) | inversion, eversion |

Knee rotation happens only with the knee bent (about 20 to 30° inward, 30 to 40° outward); it's
trained in mobility and knee rehab work, such as seated tibial rotations.

**Patterns (approved 2026-10-11): 15.** No single scientific standard exists; this follows
coaching consensus (Dan John, John Rusin) and the anti-movement model for core training.

| Kind | Patterns |
|---|---|
| Lower body | Squat, Hinge, Lunge |
| Push | Horizontal Push, Vertical Push |
| Pull | Horizontal Pull, Vertical Pull |
| Whole body | Carry, Jump, Throw |
| Trunk | Rotation, Anti-Rotation, Anti-Extension, Anti-Flexion, Anti-Lateral Flexion |

- Compound or isolation is the Type field, not a pattern. Isolation exercises have no pattern;
  their joint actions describe them (a crunch is trunk flexion).
- An exercise can have more than one pattern: a thruster is Squat and Vertical Push.
- No Locomotion pattern: sprints, crawls and sled pushes have no pattern.

### 3. Variations (approved 2026-10-11)

Grip, stance, arm and angle variations are their own exercises ("Lat Pulldown (Cable, Neutral
Grip)"), as Hevy does. Each variation has its own muscles (incline press: Upper Chest primary).
The family is the name before the brackets, so Progress can show "Lat Pulldown" together or
apart without a parent field (dropped 2026-10-11: it duplicated the name, and grouping
differently named exercises like Preacher Curl and Bayesian Curl would mix loads that don't
compare). It can be added later as one optional column.

Range of motion and pauses are not variations: bottom-half reps are partial reps on the full
exercise, and a pause is tempo. The app has no tempo input yet (`rep_tempo` is free text filled
only by the old text extraction); adding one is a separate change.

### 4. Where the library comes from

free-exercise-db (public domain, about 800 exercises, 17 muscles, push/pull, compound/isolation,
equipment) as the starting data. A script maps it onto our lists; the result is a reviewed file in
the repo, and only exercises worth keeping go in (about 150 to 200 to start). Apoorva reviews the
list. Nothing is fetched at runtime.

### 5. A person's own exercises

Allowed, for anything the library lacks. They belong to the person who made them, live in
`user_exercises`, and nobody else sees them; they never change the shared library. Creating one
asks for the primary muscles, equipment and measures (all required); the rest is optional. Own exercises count in Progress and recovery like library ones.
Names people create are reviewed from time to time and added to the library.

### 6. Logging

The exercise name box becomes a search over the library and the person's own exercises, kept on
the phone so it works offline (the plan from `db-redesign-plan.md`). The library isn't part of the
app build: once the app has loaded and gone idle, it fetches the library and the person's own
exercises and saves them on the phone. Later opens ask the server whether the library has changed;
the answer is "no change" unless we edited it. Searching never goes to the server. A new own
exercise is saved on the phone and sent to the server. Picking one fills last time's
sets in grey (history prefill). Not found: "Add Your Own". The picker's look is a visual change:
mockup first, approved before it's built.

### 7. Existing logs

Every `user_exercises` entry gets linked to a library exercise (or becomes an own exercise with its
primary muscles). A mapping file lists each name and its match; Apoorva reviews it. Stored names are
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

- [x] 1. Design approval: fields, the three lists, variations (sections 1 to 3).
- [ ] 2. Library data: `src/traininglogs/db/exercise_library.yaml`, built from the names people
      log (batch 1: the 107 local names merged into exercises; batch 2: gaps up to 150 to 200,
      found in free-exercise-db, which is also the cross-check for muscles). Names are movement
      first, equipment in brackets: "Lateral Raise (Cable)". No abbreviations, Title Case.
- [ ] 3. Schema and loading: new fields, the lists as checks, library loaded; tests.
- [ ] 4. Own exercises: `POST /exercises` with required primary muscles, equipment and
      measures; tests.
- [ ] 5. Linking existing logs: mapping file reviewed, dry run on a prod copy, prod run approved.
- [ ] 6. Reads by exercise: Progress, Key Lifts, History, new endpoints, old ones kept; tests.
- [ ] 7. Picker: mockup approved, then built, with history prefill on pick; tests, checked on
      the phone.
- [ ] 8. Effort fix (can go any time): checking a set doesn't ask for effort when it has one.
- [ ] 9. Release.
- [ ] 10. Second tier (after the release): when nothing in the library or the person's own
      exercises matches, search free-exercise-db's full list (about 870) on the server, online
      only. The list is loaded into our database, not fetched from GitHub while the app runs. A pick is copied into the person's own exercises, its 17 muscles mapped roughly onto
      ours; it never goes into the shared library directly. Picks are counted, and the most
      picked are reviewed for adding to the library.

Then the guide (`guide-plan.md`): clips recorded on the new picker.

## ▶ Resume here

2026-10-11: plan written and committed on `exercises/library` (from dev at `d5481a4`, local
only, not pushed). Step 1 done: sections 1 to 3 approved (fields, 36 muscles in 17 groups, 44
joint actions, 15 patterns, variations as their own exercises, family from the name). Nothing built.

Step 2 in progress on `exercises/library-2-data`. Batch 1 done: Apoorva's 107 names merged into
84 exercises in `src/traininglogs/db/exercise_library.yaml`, every field filled and checked
against the approved lists; sources in `ACKNOWLEDGMENTS.md`. 100 of the 107 names link through
other names; the 7 generic ones (walking lunge, shoulder press, calf raise, chest-supported row,
incline press, bicep curl, tricep extension) are matched by hand in step 5's mapping file.

Next: batch 2, the gaps up to 150 to 200 (dips, hip thrust, carries, jumps, throws, Olympic
lifts, neck, serratus, rotator cuff, obliques), searched in free-exercise-db. Present them by
region for review before writing, one exercise per row.

2026-10-11 (later): a list of 82 names in 15 regions was proposed in chat, not yet approved.
Open: keep it or trim to the most popular only; drop conditioning (run, rowing machine, bike,
sleds) because its sets would distort weekly muscle totals (recommended); medicine ball, trap bar,
sled, box and jump rope as equipment "other" or new values. Also agreed: section 5 (own
exercises stay private) and section 6 (library fetched after load, kept on the phone), and step 10
(second tier). Separate idea, not in this plan: optional AI during a session (button, speak or
type, like the corrections card) with a per-person daily cap and a monthly spend cap; add it to
`~/Projects/PLAN.md` once the library ships, Groq first.

Rules settled while writing batch 1 (also in the file's header):
- Other names only hold spellings that can mean just that exercise; generic names link only
  where there's a clear convention (bench press, squat, deadlift, lateral raise).
- Equipment is bodyweight only when nothing is added; weighted versions use other.
- Forearm Flexors only where grip commonly limits the set.
- Pauses are tempo, bottom-half reps are partial reps. Follow-up outside this plan: the app has
  no tempo input.

Context for the next session:
- Work in the worktree `~/Projects/traininglogs-wave`, not `~/Projects/traininglogs` (that one is
  on an unrelated `codebase-cleanup-...` branch).
- The local database runs in the main checkout's container `traininglogs-db_test-1` (port 5433);
  `docker compose up` from this worktree fails because the port is taken. Read it with
  `docker exec traininglogs-db_test-1 psql -U traininglogs -d traininglogs_dev`.
- This worktree has no `.venv`; `../traininglogs/.venv/bin/python` has PyYAML for checking the
  library file.
- Prod runs 5.0.0 (released 2026-10-11). The local data copy (`traininglogs_dev`, port 5433) has
  107 exercise names for one person, 23 linked; prod has a few more people.
- The Title Case change (program templates now "Bench Press", "Upper / Lower") is on `docs/guide`,
  not on dev yet. If this branch touches `program_templates.py`, merge `docs/guide` first or
  expect a conflict.
- The effort fix (step 8) is a one-line change in `screens/session/Session.tsx` `tick()`: ask
  for effort only when `set.rpe == null`, plus a test.
- The guide waits for this plan (`guide-plan.md`).
