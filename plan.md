# Implementation plan — data model flexibility + activity support

Temporary working file. Delete after this wave ships.

Full design spec and testing plan: `CHANGELOG.md` → `[Unreleased]` section.

---

## Before you start — files to read

| What | File |
|---|---|
| Full design decisions + testing plan | `CHANGELOG.md` → `[Unreleased]` |
| Current model code (what you're changing) | `src/traininglogs/models/models_v2.py` |
| Current DB schema (what you're migrating) | `src/traininglogs/db/schema.sql` |
| Current insert logic (needs updating after model change) | `src/traininglogs/db/insert_v2.py` |
| Current processor (needs lbs conversion) | `src/traininglogs/processor/processor_v2.py` |
| Existing model tests (port + extend) | `tests/test_models_v2.py` |
| Existing DB + processor tests | `tests/test_db_v2.py`, `tests/test_processor_v2.py` |
| Sample input logs (reference format) | `input_training_logs_md/` |

---

## Step 1 — model changes (`src/traininglogs/models/models_v2.py`)

Order matters — work top to bottom, each class depends on the ones above it.

- [ ] Add `Rest(BaseModel)` — `minutes: Optional[int]`, `seconds: Optional[int]`,
      validators for range, model validator rejecting both set simultaneously.
- [ ] Add `UnilateralReps(BaseModel)` — `left: Optional[RepCount]`,
      `right: Optional[RepCount]`.
- [ ] Refactor `WorkingSet` into base class — keep only `number`, `rpe`,
      `rest: Optional[Rest]`, `notes`. Move shared validators here.
- [ ] Add `StrengthSet(WorkingSet)` — `set_type: Literal["strength"] = "strength"`,
      `weight_kg`, `rep_count`, `unilateral_rep_count`, `rep_quality_assessment`,
      `failure_technique`. Move `failure_technique_requires_rpe_10` validator here.
- [ ] Add `ActivitySet(WorkingSet)` — `set_type: Literal["activity"] = "activity"`,
      `duration_seconds`, `distance_meters`, `heart_rate_bpm`.
- [ ] Add `AnySet` discriminated union (`StrengthSet | ActivitySet` on `set_type`).
- [ ] Update `Goal` — make `weight_kg`, `sets`, `rep_range` Optional; replace
      `rest_minutes: Optional[int]` with `rest: Optional[Rest]`; add
      `distance_meters: Optional[float]`, `target_duration_seconds: Optional[int]`.
- [ ] Update `Exercise` — rename `working_sets` → `sets: Optional[List[AnySet]]`;
      add `exercise_type: Literal["strength", "activity"] = "strength"`.
- [ ] Update `TrainingSession` — make `program`, `program_author`,
      `program_length_weeks`, `phase`, `week`, `is_deload_week`, `focus`,
      `session_duration_minutes` all Optional; add
      `weight_unit: Literal["kg", "lbs"] = "kg"`. Update validators that
      reference these fields (e.g. `week` range check requires `program_length_weeks`
      to be non-None).

---

## Step 2 — unit tests (`tests/test_models_v2.py`)

Run `docker compose up -d` first (DB tests need Postgres, model tests do not but
run them together to catch early breakage).

Run: `.venv/bin/pytest tests/test_models_v2.py -v`

- [ ] Port all existing `WorkingSet` tests to `StrengthSet`.
- [ ] Add `Rest` tests (see CHANGELOG testing plan for full list).
- [ ] Add `UnilateralReps` tests.
- [ ] Add `ActivitySet` tests.
- [ ] Add `AnySet` discriminator dispatch tests.
- [ ] Add `Goal` tests for new Optional fields and `Rest`.
- [ ] Add `TrainingSession` tests for ad-hoc session and `weight_unit`.

All existing tests must still pass. Fix any that break before moving forward.

---

## Step 3 — DB migration (`src/traininglogs/db/schema.sql`)

Write as `ALTER TABLE` statements — additive only, no drops.

- [ ] `working_sets`: add `set_type`, `duration_seconds`, `distance_meters`,
      `heart_rate_bpm`, `left_reps_full`, `left_reps_partial`, `right_reps_full`,
      `right_reps_partial`, `rest_seconds`. Keep existing `rest_minutes`.
- [ ] `sessions`: add `weight_unit TEXT NOT NULL DEFAULT 'kg'`.
- [ ] `exercises`: add `exercise_type TEXT NOT NULL DEFAULT 'strength'`.

Apply to test DB: `docker compose up -d` then run migration manually or via a
script. Verify with `\d working_sets` in psql.

---

## Step 4 — insert logic (`src/traininglogs/db/insert_v2.py`)

- [ ] Update working set insert to write `set_type` and route fields correctly:
      `StrengthSet` → existing columns + unilateral columns;
      `ActivitySet` → `duration_seconds`, `distance_meters`, `heart_rate_bpm`,
      `rest_seconds`.
- [ ] Update `Rest` serialization — write to `rest_minutes` or `rest_seconds`
      depending on which is set.
- [ ] Update session insert to write `weight_unit`.
- [ ] Update exercise insert to write `exercise_type`.
- [ ] Update `Goal` insert for new Optional fields and `rest` → `rest_minutes`.

Run: `.venv/bin/pytest tests/test_db_v2.py -v`

---

## Step 5 — processor (`src/traininglogs/processor/processor_v2.py`)

Unit is specified in the Goal line of each exercise (`135 lbs x 3 sets x 8-10 reps`).
If no unit is present, default is kg. The parser reads the unit from the Goal line
and applies it to all sets in that exercise. Conversion happens in the parser/processor
before the model is built — the model always receives kg.

- [ ] In the Goal line parser: extract unit (`kg` or `lbs`) alongside weight.
      Pass unit through to the exercise-level context.
- [ ] Before building `StrengthSet.weight_kg` and `Goal.weight_kg`: if unit is
      `lbs`, multiply by 0.453592 and round to 3 decimal places.
- [ ] `TrainingSession.weight_unit` records the original unit as metadata but all
      stored weights are always kg.

Run: `.venv/bin/pytest tests/test_processor_v2.py -v`

---

## Step 6 — parser syntax decisions (design step, before writing code)

The parser (`parser/extract.py`, `parser/parse.py`) is rule-based. New fields
need a markdown syntax decision before any code is written. Do not skip this step.

Questions to answer:
- What does an activity exercise block look like in markdown?
- What does a unilateral set look like in markdown?
- Where does `weight_unit` appear — per-session header, per-exercise, per-set?

Write two or three sample input log files in `input_training_logs_md/` covering
the new cases, agree on the format, then update the parser.

---

## Step 7 — end-to-end validation (manual)

Run the full pipeline against the test DB using the sample inputs from Step 6.

```bash
docker compose up -d
traininglogs log --dry-run          # preview first
traininglogs log --no-commit        # insert without git commit
```

Check:
- [ ] JSON files written to `output_training_logs_json/` — inspect manually.
- [ ] DB rows correct — spot-check with psql.
- [ ] Existing sessions unaffected — re-run a known-good historical log and
      confirm output matches pre-change baseline.

---

## Done

- [ ] All tests pass: `.venv/bin/pytest tests/ -v`
- [ ] JSON output manually validated for all five sample input types.
- [ ] Move `[Unreleased]` entries in `CHANGELOG.md` under a new version heading.
- [ ] Delete this file.
