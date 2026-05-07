# Refactor: drop the dataclass bridge

**Goal:** collapse the two-model-layer pipeline. `parse.py` currently builds old
dataclass objects that `processor.py` serialises to dicts and patches up before
Pydantic validation. The bridge has caused two silent data bugs and requires every
schema change to be applied in three places. After this refactor, `parse.py`
produces dicts shaped directly for `model_validate()` — one model layer, no bridge.

**Base branch:** `refactor/drop-dataclass-bridge` (cut from `dev`)  
**Merge target:** `dev` — only after all steps green and 147/0 suite.

**Rule:** one sub-branch per step, squash-merged back to base. Never commit
directly to the base branch. Suite must be 147 passing (0 skipped, 0 failed)
before each squash-merge.

---

## Blast radius (audited 2026-05-07)

Files that import or use `models_dataclass`:

| File | What it does |
|---|---|
| `src/traininglogs/parser/parse.py` | Produces dataclass objects (`TrainingSession`, `Exercise`, `WorkingSet`, `WarmupSet`, `Goal`, …) |
| `src/traininglogs/processor/processor.py` | `_to_primitive()` serialises them; bridge loop patches the dict |
| `tests/test_parse.py` | 6 `isinstance` checks against `Goal`, `WorkingSet`, `WarmupSet` |

Nothing else. `models_dataclass.py` itself can be deleted in Step 3.

---

## Steps

### Step 1 — `refactor/parse-returns-dict`

**Change:** `DeepTrainingParser._parse_*` methods return plain dicts shaped for
Pydantic. No dataclass objects constructed at all.

Specific changes in `parse.py`:
- `_parse_working_set_line()`: return dict with `set_type: "strength"` already set
  (unilateral sets already return a dict — unify to always return dict).
- `_parse_activity_set_line()`: already returns dict — no change.
- `_parse_warmup_set_line()`: return dict `{number, weight_kg, rep_count, notes}`.
- `_parse_goal()`: return dict with `rest: {minutes: X}` instead of
  `Goal(rest_minutes=X)`.
- `build_training_session()`: return a plain dict (not a dataclass `TrainingSession`).
- Remove all `from traininglogs.models.models_dataclass import …` in `parse.py`.

**Tests (`tests/test_parse.py`):**
- Replace `isinstance(ws, WorkingSet)` → assert dict with correct keys/values.
- Replace `isinstance(ws, WarmupSet)` → assert dict.
- Replace `isinstance(g, Goal)` → assert dict.
- No test deleted. Same scenarios, same assertions — just dict not dataclass.

- [ ] Branch cut
- [ ] Code changed
- [ ] Tests updated (all 147 pass)
- [ ] Squash-merged to base

---

### Step 2 — `refactor/processor-drop-bridge`

**Change:** `processor.py` drops `_to_primitive()`, the rename/inject loop,
and the rest-mapping bridge. `DeepTrainingParser` now returns a dict directly,
so `processor.py` just:
1. Gets the dict from `DeepTrainingParser.build_training_session()`
2. Injects `session_id`
3. Handles lbs→kg conversion
4. Calls `TrainingSession.model_validate(d)`

Remove: `_to_primitive()`, `is_dataclass` import, bridge loop, the bridge comment.

**Tests:** run suite — verify 147/0. No test changes expected (processor tests,
if any, test the full `process_md_file` pipeline which is behaviour-stable).

- [ ] Branch cut
- [ ] Code changed
- [ ] Tests pass (147/0)
- [ ] Squash-merged to base

---

### Step 3 — `refactor/delete-models-dataclass`

**Change:** delete `src/traininglogs/models/models_dataclass.py`. Remove any
remaining imports (should be none after Step 1 + 2). Verify with:
```bash
grep -rn "models_dataclass" src/ tests/ scripts/
```
Expected: no output.

**Tests:** suite must be 147/0. Any `ImportError` or `NameError` will surface here.

- [ ] Branch cut
- [ ] File deleted, imports cleaned
- [ ] Tests pass (147/0)
- [ ] Squash-merged to base

---

### Step 4 — `refactor/docs-update`

**Change (docs only, no app code):**
- `docs/design.html`: update pipeline section — remove "legacy dataclass shape"
  sentence, describe single-layer flow.
- `CHANGELOG.md`: add entry under `[Unreleased]`.
- `CLAUDE.md`: remove any reference to the bridge or dataclass intermediate repr.

- [ ] Branch cut
- [ ] docs/design.html updated
- [ ] CHANGELOG.md updated
- [ ] CLAUDE.md updated
- [ ] Squash-merged to base

---

### Final

- [ ] Full suite green on base branch (147/0)
- [ ] Base branch squash-merged to `dev`
- [ ] `migration-plan.md` resume pointer updated

---

## ▶ Resume here

**Not started. Cut base branch first:**
```bash
git checkout dev
git checkout -b refactor/drop-dataclass-bridge
```
Then start Step 1.
