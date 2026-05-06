"""Compare output_training_logs_json (old) vs output_training_logs_json_v2 (new).

Reports ALL differences between every matched JSON pair, labeled as:
  EXPECTED — known structural change from the v2 model refactor (not data loss)
  SUSPICIOUS — any actual value change; requires manual review before sign-off

Expected structural changes (labeled, not hidden):
  1. data_model_version value changed
  2. weight_unit: (absent/None) → 'kg'  [new top-level field]
  3. exercises[*].working_sets removed; exercises[*].sets added  [key rename]
  4. exercises[*].exercise_type added  [new discriminator field]
  5. exercises[*].sets[*].set_type added  [new discriminator field]
  6. current_goal.rest_minutes → current_goal.rest  [rename]
     current_goal.distance_meters, target_duration_seconds added  [new activity fields]
  7. warmup_sets: [None, ...] → [...] (None entries from failed parses cleaned up)

Exit 0 if all diffs are EXPECTED, 1 if any SUSPICIOUS.
"""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OLD_DIR = PROJECT_ROOT / "output_training_logs_json"
NEW_DIR = PROJECT_ROOT / "output_training_logs_json_v2"


Diff = tuple[str, str, object, object]  # (label, location, old_val, new_val)


def index_by_session_id(root: Path) -> dict[str, Path]:
    return {
        json.loads(p.read_text())["session_id"]: p
        for p in root.rglob("*.json")
    }


def classify_top_level(key: str, old_val, new_val) -> str:
    if key == "data_model_version":
        return "EXPECTED"  # version bump
    if key == "weight_unit" and old_val is None and new_val == "kg":
        return "EXPECTED"  # new field stamped by v2 model
    return "SUSPICIOUS"


def classify_exercise_field(key: str, old_val, new_val) -> str:
    if key == "exercise_type":
        return "EXPECTED"  # new discriminator field
    if key == "working_sets" and new_val is None:
        return "EXPECTED"  # old field removed in v2 (replaced by 'sets')
    if key == "sets" and old_val is None:
        return "EXPECTED"  # new field added in v2 (replaces 'working_sets')
    return "SUSPICIOUS"


def classify_goal_field(key: str, old_val, new_val) -> str:
    if key == "rest_minutes" and new_val is None:
        return "EXPECTED"  # renamed to 'rest' in v2
    if key in ("rest", "distance_meters", "target_duration_seconds") and old_val is None:
        return "EXPECTED"  # new fields in v2 goal model
    return "SUSPICIOUS"


def classify_set_field(key: str, old_val, new_val) -> str:
    if key == "set_type":
        return "EXPECTED"  # new discriminator field
    return "SUSPICIOUS"


def diff_dicts(old: dict, new: dict, classify_fn, location: str) -> list[Diff]:
    diffs = []
    for k in sorted(set(old) | set(new)):
        ov, nv = old.get(k), new.get(k)
        if ov != nv:
            label = classify_fn(k, ov, nv)
            diffs.append((label, f"{location}.{k}", ov, nv))
    return diffs


def diff_sets(old_sets: list, new_sets: list, location: str) -> list[Diff]:
    diffs = []
    # Filter None entries from old (failed parse, cleaned up in v2)
    old_clean = [(i, s) for i, s in enumerate(old_sets) if s is not None]
    new_clean = [(i, s) for i, s in enumerate(new_sets) if s is not None]

    # Report any None entries that were cleaned
    old_nones = [i for i, s in enumerate(old_sets) if s is None]
    if old_nones:
        diffs.append(("EXPECTED", f"{location}[None entries at indices {old_nones}]",
                      "None entry in old", "removed in new"))

    if len(old_clean) != len(new_clean):
        diffs.append(("SUSPICIOUS", f"{location} count",
                      f"{len(old_clean)} non-None sets", f"{len(new_clean)} sets"))
        return diffs

    for (oi, os), (ni, ns) in zip(old_clean, new_clean):
        diffs.extend(diff_dicts(os, ns, classify_set_field, f"{location}[{oi}]"))

    return diffs


def compare_sessions(old_path: Path, new_path: Path) -> list[Diff]:
    old = json.loads(old_path.read_text())
    new = json.loads(new_path.read_text())
    diffs: list[Diff] = []

    # Top-level fields
    old_top = {k: v for k, v in old.items() if k != "exercises"}
    new_top = {k: v for k, v in new.items() if k != "exercises"}
    diffs.extend(diff_dicts(old_top, new_top, classify_top_level, "top"))

    # Exercises
    old_exs = old.get("exercises", [])
    new_exs = new.get("exercises", [])
    if len(old_exs) != len(new_exs):
        diffs.append(("SUSPICIOUS", "exercises count", len(old_exs), len(new_exs)))
        return diffs

    for i, (oe, ne) in enumerate(zip(old_exs, new_exs)):
        name = oe.get("name", f"ex{i+1}")
        prefix = f"exercises[{i}] ({name})"

        # Exercise-level fields (excluding nested collections handled separately)
        skip = {"warmup_sets", "working_sets", "sets", "current_goal"}
        old_ex_flat = {k: v for k, v in oe.items() if k not in skip}
        new_ex_flat = {k: v for k, v in ne.items() if k not in skip}
        diffs.extend(diff_dicts(old_ex_flat, new_ex_flat, classify_exercise_field, prefix))

        # working_sets → sets rename: report as expected structural change
        if "working_sets" in oe and "sets" in ne:
            diffs.append(("EXPECTED", f"{prefix} key rename",
                          "working_sets", "sets"))

        # Working sets data comparison (old: working_sets, new: sets)
        old_ws = oe.get("working_sets") or []
        new_ws = ne.get("sets") or []
        diffs.extend(diff_sets(old_ws, new_ws, f"{prefix}.working_sets→sets"))

        # current_goal
        og = oe.get("current_goal") or {}
        ng = ne.get("current_goal") or {}
        diffs.extend(diff_dicts(og, ng, classify_goal_field, f"{prefix}.current_goal"))

        # Warmup sets
        old_warmup = oe.get("warmup_sets") or []
        new_warmup = ne.get("warmup_sets") or []
        diffs.extend(diff_sets(old_warmup, new_warmup, f"{prefix}.warmup_sets"))

    return diffs


def main() -> None:
    print(f"Old: {OLD_DIR}")
    print(f"New: {NEW_DIR}\n")

    old_index = index_by_session_id(OLD_DIR)
    new_index = index_by_session_id(NEW_DIR)

    only_old = set(old_index) - set(new_index)
    only_new = set(new_index) - set(old_index)
    both = set(old_index) & set(new_index)

    has_suspicious = False

    if only_old:
        has_suspicious = True
        print(f"MISSING FROM NEW ({len(only_old)}):")
        for sid in sorted(only_old):
            print(f"  - {sid}")
        print()

    if only_new:
        has_suspicious = True
        print(f"ONLY IN NEW ({len(only_new)}):")
        for sid in sorted(only_new):
            print(f"  - {sid}")
        print()

    print(f"Comparing {len(both)} matched sessions...\n")

    session_diffs: dict[str, list[Diff]] = {}
    for sid in sorted(both):
        diffs = compare_sessions(old_index[sid], new_index[sid])
        if diffs:
            session_diffs[sid] = diffs

    total_expected = 0
    total_suspicious = 0

    for sid, diffs in session_diffs.items():
        suspicious = [d for d in diffs if d[0] == "SUSPICIOUS"]
        expected = [d for d in diffs if d[0] == "EXPECTED"]
        total_expected += len(expected)
        total_suspicious += len(suspicious)
        if suspicious:
            has_suspicious = True
        print(f"  {sid}  ({len(expected)} expected, {len(suspicious)} suspicious)")
        for label, loc, ov, nv in diffs:
            marker = "!" if label == "SUSPICIOUS" else "~"
            print(f"    [{label}] {marker} {loc}")
            print(f"        old: {ov!r}")
            print(f"        new: {nv!r}")

    print("\n" + "=" * 60)
    print(f"  Matched sessions : {len(both)}")
    print(f"  Sessions w/ diffs: {len(session_diffs)}")
    print(f"  Expected diffs   : {total_expected}")
    print(f"  Suspicious diffs : {total_suspicious}")
    print(f"  Missing from new : {len(only_old)}")
    print(f"  Only in new      : {len(only_new)}")
    print("=" * 60)

    if has_suspicious:
        print("\nSuspicious differences found. Review above before sign-off.")
        sys.exit(1)
    else:
        print("\nAll clear. Every difference is an expected structural change.")
        print("No data values (weights, reps, dates, names) were corrupted.")
        sys.exit(0)


if __name__ == "__main__":
    main()
