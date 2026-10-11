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
| Other names | any number | no | how people write it: "bench", "bb bench"; search words only, never used to link (changed 2026-10-11) |
| Equipment | one | yes | barbell, ez bar, trap bar, dumbbell, kettlebell, cable, machine, smith machine, band, medicine ball, sled, box, jump rope, bodyweight, other |
| Measures | one or more | yes | weight, reps, time, distance |
| Compound | one | no | yes (moves two or more joints) or no (isolation); `compound` in the database, renamed from Type 2026-10-11 so it can't be mistaken for patterns |
| Primary muscles | one or more | yes | from the muscle list; each counts 1 set |
| Secondary muscles | any number | no | from the muscle list; each counts 0.5 sets |
| Joint actions | any number | no | from the joint action list, e.g. hip extension, knee extension |
| Patterns | any number | no | from the pattern list; isolation exercises have none |
| free-exercise-db id | one | no | the matching free-exercise-db exercise, "Barbell_Hip_Thrust"; empty when it has none (section 4) |

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
triceps 1.5. This is the "fractional" method that fit best in Pelland et al. (Sports Medicine
2026, meta-regression of 67 studies). Weekly sets per muscle and recovery tracking read these
totals.

**Counting by group (agreed 2026-10-11):** Pelland and Fitbod count chest or triceps as one
muscle. Our groups split some (Upper Chest and Mid/Lower Chest, two triceps muscles), so adding
them would count one set twice: a pressdown would give triceps 2. A group's count for a set is
its highest muscle: 1 if any of its muscles is primary, 0.5 if only secondary, 0 otherwise. So
a bench press set gives chest 1 and triceps 0.5. The per-muscle numbers stay for detail.

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

**Keeping their data apart from ours (approved 2026-10-11).** Their rows and our library are
separate tables, linked by their id:

```
free_exercise_db                  exercises (our library)
----------------                  -----------------------
id  text  primary key   <------   free_exercise_db_id  text  null, references free_exercise_db(id)
name                              name, equipment, muscles ... (ours, curated)
primary_muscles, secondary_muscles
equipment, mechanic, force, level
instructions, images
```

- `free_exercise_db` holds their rows unchanged, with their column names; nobody edits it by
  hand. It's loaded from one pinned commit of their repo (they have no releases), recorded in
  the loader, so a reload gives the same ids and an update is a reviewed change.
- `exercises.free_exercise_db_id` links our exercise to theirs; the foreign key makes a mistyped
  id fail at load. Empty where they have no match.
- Their data never fills our columns. Our muscles stay our 36; theirs are for cross-checking.
  Their images and instructions are reachable through the link; only the paths are stored for
  now (the images sit on GitHub). Showing them is a visual change and needs Apoorva's yes.
- No generic sources table: there is one source. A second one would get its own table and column.

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

### 9. v1 scope (agreed 2026-10-11)

Built and tried locally against the dev copy of prod before staging. On top of sections 5 to 8:

- **My Exercises**, one screen: your own exercises and any names not linked to the library.
  Each row offers "Link to a library exercise" or "Keep as my own" (which asks for primary
  muscles, equipment and measures). Step 5's mapping becomes a pre-fill reviewed there. Needed
  because names that arrive as text (notes, old app) keep arriving unlinked.
- **Progress redesign**: an overview of tiles, each doing one job (strength, volume per muscle
  group, what hasn't been trained, and others), each opening a sub-page. Metrics and visuals
  come from a research pass (2026-10-11), then a mockup approved before building. Agreed so far:
  - Volume per muscle group shows the counts only, no target bands.
  - Strength against bodyweight for the key lifts (deadlift, squat, bench press, pull-up, row)
    and bodyweight maxes such as most pull-ups: "squat 2.2x bodyweight".
    The number is the estimated max (Epley with RPE, as Progress uses now) over the bodyweight
    on that date, with "heaviest lifted 140 kg × 5" underneath. Pull-up (Bodyweight) shows best
    reps only; Pull-up (Weighted) is its own exercise and its estimated max is the added weight
    alone. Bodyweight is never added to a lift's load.
  - A Skills tile: best hold time or best clean reps. Each person picks their skills in
    Settings, like Key Lifts, starting from a default list.
  - A front and back body map with `body-highlighter` (MIT).
  - Left out: recovery percentages, tonnage across exercises, composite scores.
  - Chart details are decided on mockups.
- **Profile**: bodyweight (the person updates it when it changes; each update kept with its
  date, so past ratios use the weight at the time), height, and date of birth (age is worked
  out from it).
- **Linking**: past names show the library name once linked (History, Progress, sessions); the
  typed name shows on My Exercises. Linking an own exercise to a library one makes the library's
  muscles, equipment and measures count, past sets included; the own version is kept, so
  unlinking restores it; both show what changes and offer Undo.
- **Picker**: the exercise name box searches as you type (names and other names, library and
  your own, on the phone), with a list under it; nothing shows before typing. Picking a row is
  the link. The last row is always "Add '…' as your own". Same box in sessions and workout
  plans. The set row shows the exercise's measures (time and distance boxes are new; the
  database already stores both).
- **Add your own**: one sheet, simplest first. Required: name and at least one primary muscle
  (picked by group, then muscle). Measures start as weight and reps. Optional, under "More
  details": equipment, secondary muscles, compound, joint actions (grouped by joint), patterns.
  Equipment is optional for own exercises (no metric uses it).
- Not in v1: the second tier. Later, "Link to a library exercise" on My Exercises also searches
  `free_exercise_db` on the server.

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
- [x] 2. Library data: `src/traininglogs/db/exercise_library.yaml`, built from the names people
      log (batch 1: the 107 local names merged into exercises; batch 2: gaps up to 150 to 200,
      found in free-exercise-db, which is also the cross-check for muscles). Names are movement
      first, equipment in brackets: "Lateral Raise (Cable)". No abbreviations, Title Case.
      Every exercise gets `free_exercise_db_id` where they have a match (batch 1 filled in
      afterwards), reviewed by Apoorva.
- [ ] 3. Schema and loading: new fields, the lists as checks; the `free_exercise_db` table
      loaded from a pinned commit, then the library with its foreign key, unique (one of
      theirs links to one of ours at most); tests. Agreed 2026-10-11:
      - `schema.sql` holds the lists as domains and the equipment check; the database refuses
        a value not on them, whoever writes it. Adding to a list is a `schema.sql` change.
      - `movement` and `muscles` are dropped (nothing reads them; Apoorva's one-off exception
        to never dropping in place). The starter insert comes out of `schema.sql`.
      - `scripts/load_exercise_library.py`, run by hand. It does everything in one transaction
        and rolls back unless given `--apply`, printing what it added, renamed and updated.
        Matches by exact name; never deletes (lists rows not in the file).
      - The 32 starter rows are renamed from an explicit list of pairs Apoorva reviews, keeping
        their ids; each old name goes into the new row's other names.
      - free-exercise-db: their `dist/exercises.json` at commit `f00c92c` kept as plain text in
        `scripts/data/`, loaded by the same script, never edited.
      - Rollout: tests, then local dev (a prod copy), then staging (a fresh prod copy), checking
        every link points at the same row id and no counts moved. Prod at the release (step 9).
      - Hard linking only: other names are search words, never used to link, and can repeat
        across exercises. The server links a typed name only when it is exactly a library name
        (`db/insert.py`); anything else becomes the person's own exercise until they pick one
        (step 7) or step 5's reviewed mapping links it. Already-linked names stay linked.
      - Names that arrive as text (notes read by the AI, phones on the old app) become own
        exercises for now. Follow-up after the picker: the AI's confirmation card asks the
        person to pick the exercise for each name.
      - For step 4: own exercises pick equipment from the list; "other" asks what it is and
        stores the text in `equipment_other`.
- [ ] 4. Own exercises: `POST /exercises` with required primary muscles, equipment and
      measures; tests.
- [ ] 5. Linking existing logs: mapping file reviewed, dry run on a prod copy, prod run approved.
- [ ] 6. Reads by exercise: Progress, Key Lifts, History, new endpoints, old ones kept; sets
      counted by group as in section 1; tests.
- [ ] 7. Picker: mockup approved, then built, with history prefill on pick; tests, checked on
      the phone.
- [ ] 8. Effort fix (can go any time): checking a set doesn't ask for effort when it has one.
- [ ] 9. Release.
- [ ] 10. Second tier (after the release): when nothing in the library or the person's own
      exercises matches, search the `free_exercise_db` table (about 870) on the server, online
      only. A result that a library exercise links to shows that library exercise instead
      ("glute ham raise" finds `Floor_Glute-Ham_Raise`, which shows Nordic Curl). A pick is
      copied into the person's own exercises with `user_exercises.free_exercise_db_id` set, its 17 muscles mapped
      roughly onto ours; it never goes into the shared library directly. Picks are counted by
      grouping on that column, and the most picked are reviewed for adding to the library.

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

2026-10-11 (later): batch 2 names approved: 77 in 14 regions (the proposed 82 minus
conditioning, dropped because its sets would distort weekly muscle totals; a follow-up). Equipment
gained trap bar, medicine ball, sled, box and jump rope. `free_exercise_db_id` approved (section
4). Batch 2 written: all 77, 161 in the file, checked by script against the lists (names,
other_names, ids, muscles, joint actions, patterns, equipment). Apoorva reviews the judgment
calls. Second pass done (2026-10-11): every muscle must be moved by a listed joint action
(anatomy references) or measured in a cited study; 56 exercises trimmed, Transverse Abdominis
no longer listed on any exercise, rules written in the file header. The check scripts are not in
the repo yet; step 3's loader tests should carry the list and joint-action checks. Batch 1 ids
filled: 53 of 84 matched (110 of 161 overall), each checked against their instructions; the rest
are variations they lack; Apoorva approved them. Step 2 squashed into `exercises/library` as
`c8fb8a6` (suite green, 743 passed).

2026-10-11 (step 3): design agreed (see step 3 in Steps) and written on
`exercises/library-3-schema`: `schema.sql` (lists as domains, `free_exercise_db`, new columns,
`movement` and `muscles` dropped, starter insert removed), `db/library.py`,
`scripts/load_exercise_library.py`, `scripts/data/free_exercise_db.json`, exact-name linking in
`db/insert.py`, `tests/test_exercise_library.py`, pyyaml in the dev lock (hand-inserted: no Python
3.12 on this Mac, and pip-compile on 3.13 rewrites other lines). Suite green: 767 passed, on the
existing test database and on a fresh one. Dry run on local dev: 32 renamed, 129 added, 32
updated, 0 left alone; the 19 links point at the same row ids. Applied to local dev: everything the app reads (sessions,
history, last values, Progress, export) byte-identical before and after, counts unchanged. Step 5
must fix three old guessed links: Seated Leg Curl -> Leg Curl (Machine, Lying) is wrong; Shoulder
Press -> Overhead Press (Barbell) and Calf raise -> Calf Raise (Machine, Standing) need checking.
Apoorva wants the server and app side built and tried locally before staging. Next: staging
(fresh prod copy, `copy_prod_to_dev.py` with `DEV_DATABASE_URL="$DATABASE_URL_STAGING"`, then the
script with `--database-url`), then squash into `exercises/library`. Run scripts with
`PYTHONPATH=src ../traininglogs/.venv/bin/python`; it has PyYAML. `docs/design.html` predates
the accounts redesign; update it at the release.
exercise at most (weighted push-ups and dips have none). Matching rule: search their names and instructions, read the description,
and say "no match" only after both (their names differ: Nordic Curl is `Floor_Glute-Ham_Raise`).
Their name goes into other_names too. The free-exercise-db file for checking: `dist/exercises.json` in
github.com/yuhonas/free-exercise-db. The approved names (free-exercise-db's own names go in other_names):
- Chest: Bench Press (Dumbbell); Bench Press (Barbell, Close Grip); Incline Press (Barbell);
  Chest Press (Machine); Push-up (Bodyweight); Push-up (Weighted); Dip (Bodyweight); Dip (Weighted)
- Shoulders: Arnold Press (Dumbbell); Landmine Press (Barbell, Single Arm); Push Press (Barbell);
  Handstand Push-up (Bodyweight)
- Rotator cuff: External Rotation (Cable); External Rotation (Band); Internal Rotation (Cable)
- Serratus: Push-up Plus (Bodyweight); Serratus Punch (Cable)
- Back: Straight-Arm Pulldown (Cable); Pullover (Dumbbell); Inverted Row (Bodyweight); T-Bar Row
  (Barbell); Shrug (Barbell); Shrug (Dumbbell); Scapular Pull-up (Bodyweight); Dead Hang
  (Bodyweight); Muscle-up (Bodyweight)
- Arms: Biceps Curl (Barbell); Hammer Curl (Dumbbell); Triceps Pressdown (Cable, Rope)
- Core: Plank (Bodyweight); Side Plank (Bodyweight); Pallof Press (Cable); Woodchop (Cable); Dead
  Bug (Bodyweight); Hollow Body Hold (Bodyweight); L-sit (Bodyweight); Hanging Knee Raise
  (Bodyweight); Crunch (Bodyweight)
- Hips and glutes: Hip Thrust (Barbell); Hip Thrust (Machine); Glute Bridge (Bodyweight, Single
  Leg); Glute Kickback (Cable); Copenhagen Plank (Bodyweight)
- Legs: Front Squat (Barbell); Goblet Squat (Dumbbell); Pistol Squat (Bodyweight); Step-up
  (Dumbbell); Reverse Lunge (Dumbbell); Sumo Deadlift (Barbell); Deadlift (Trap Bar); Romanian
  Deadlift (Dumbbell); Single-Leg Romanian Deadlift (Dumbbell); Good Morning (Barbell); Nordic
  Curl (Bodyweight)
- Carries: Farmer Carry (Dumbbell); Suitcase Carry (Dumbbell); Overhead Carry (Kettlebell)
- Jumps: Box Jump; Broad Jump; Depth Jump; Jump Rope
- Throws: Slam (Medicine Ball); Chest Pass (Medicine Ball); Rotational Throw (Medicine Ball);
  Overhead Backward Throw (Medicine Ball)
- Olympic and kettlebell: Power Clean (Barbell); Hang Clean (Barbell); Snatch (Barbell); Power
  Snatch (Barbell); Clean and Jerk (Barbell); Swing (Kettlebell); Snatch (Kettlebell); Turkish
  Get-up (Kettlebell)
- Neck: Neck Curl (Plate); Neck Extension (Plate); Lateral Neck Flexion (Plate); Neck Extension
  (Harness)

Also agreed: section 5 (own
exercises stay private) and section 6 (library fetched after load, kept on the phone), and step 10
(second tier). Separate idea, not in this plan: optional AI during a session (button, speak or
type, like the corrections card) with a per-person daily cap and a monthly spend cap; add it to
`~/Projects/PLAN.md` once the library ships, Groq first.

Rules settled while writing batch 1 (also in the file's header):
- Other names only hold spellings that can mean just that exercise; generic names link only
  where there's a clear convention (bench press, squat, deadlift, lateral raise). Replaced
  2026-10-11: other names are search words only and can repeat across exercises.
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
- Prod runs 5.0.0 (released 2026-10-11). The local data copy (`traininglogs_dev`, port 5433) was
  re-copied from prod on 2026-10-11 (the old one had test data): 2 people, 99 exercise names, 19
  linked, 133 sessions, 3419 sets, the same counts as prod. The prod connection string is the
  `database-url` secret in Secret Manager; `.env` has it commented out on purpose.
- Step 3 decision (2026-10-11): the 32 starter rows in `exercises` are renamed in place to their
  library names, keeping their ids so every link holds, and each old name goes into the new
  row's other names. Leg Curl becomes Leg Curl (Machine, Lying); Pull-up, Lat Pulldown, Seated
  Cable Row and Walking Lunge go to Pull-up (Bodyweight), Lat Pulldown (Cable, Wide Grip), Row
  (Cable, Seated, Neutral Grip) and Walking Lunge (Dumbbell). Rollout: tests, then a prod copy in
  staging, checked (every link points at the same row id before and after, counts unchanged),
  then prod.
- The Title Case change (program templates now "Bench Press", "Upper / Lower") is on `docs/guide`,
  not on dev yet. If this branch touches `program_templates.py`, merge `docs/guide` first or
  expect a conflict.
- The effort fix (step 8) is a one-line change in `screens/session/Session.tsx` `tick()`: ask
  for effort only when `set.rpe == null`, plus a test.
- The guide waits for this plan (`guide-plan.md`).
