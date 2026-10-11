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
| Name | one | yes | "Barbell Bench Press" |
| Other names | any number | no | how people write it: "bench", "bb bench"; used for automatic linking only |
| Parent | one | no | the family it belongs to: "Neutral Grip Lat Pulldown" belongs to "Lat Pulldown" |
| Equipment | one | yes | barbell, dumbbell, kettlebell, cable, machine, smith machine, band, bodyweight, other |
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

Grip, stance, arm and angle variations are their own exercises ("Neutral Grip Lat Pulldown"),
linked to a parent ("Lat Pulldown"), as Hevy does. Each variation has its own muscles (incline
press: Upper Chest primary), and Progress can show the family together or apart.

### 4. Where the library comes from

free-exercise-db (public domain, about 800 exercises, 17 muscles, push/pull, compound/isolation,
equipment) as the starting data. A script maps it onto our lists; the result is a reviewed file in
the repo, and only exercises worth keeping go in (about 150 to 200 to start). Apoorva reviews the
list. Nothing is fetched at runtime.

### 5. A person's own exercises

Allowed, for anything the library lacks. Creating one asks for the primary muscles, equipment and
measures (all required); the rest is optional. Own exercises count in Progress and recovery like library ones.
Names people create are reviewed from time to time and added to the library.

### 6. Logging

The exercise name box becomes a search over the library and the person's own exercises, kept on
the phone so it works offline (the plan from `db-redesign-plan.md`). Picking one fills last time's
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
- [ ] 2. Library data: script from free-exercise-db, reviewed list of 150 to 200.
- [ ] 3. Schema and loading: new fields, the lists as checks, library loaded; tests.
- [ ] 4. Own exercises: `POST /exercises` with required primary muscles, equipment and
      measures; tests.
- [ ] 5. Linking existing logs: mapping file reviewed, dry run on a prod copy, prod run approved.
- [ ] 6. Reads by exercise: Progress, Key Lifts, History, new endpoints, old ones kept; tests.
- [ ] 7. Picker: mockup approved, then built, with history prefill on pick; tests, checked on
      the phone.
- [ ] 8. Effort fix (can go any time): checking a set doesn't ask for effort when it has one.
- [ ] 9. Release.

Then the guide (`guide-plan.md`): clips recorded on the new picker.

## ▶ Resume here

2026-10-11: plan written and committed on `exercises/library` (from dev at `d5481a4`, local
only, not pushed). Step 1 done: sections 1 to 3 approved (fields, 36 muscles in 17 groups, 44
joint actions, 15 patterns, variations as their own exercises with a parent). Nothing built.

Next: step 2, library data. Cut `exercises/library-2-data`, look at free-exercise-db's fields and
muscle names, and propose how they map onto our lists before writing the script. Its 17 muscles
are coarser than ours (no chest or trap split, no brachialis), so some mapping will be by hand.

Context for the next session:
- Prod runs 5.0.0 (released 2026-10-11). The local data copy (`traininglogs_dev`, port 5433) has
  107 exercise names for one person, 23 linked; prod has a few more people.
- The Title Case change (program templates now "Bench Press", "Upper / Lower") is on `docs/guide`,
  not on dev yet. If this branch touches `program_templates.py`, merge `docs/guide` first or
  expect a conflict.
- The effort fix (step 8) is a one-line change in `screens/session/Session.tsx` `tick()`: ask
  for effort only when `set.rpe == null`, plus a test.
- The guide waits for this plan (`guide-plan.md`).
