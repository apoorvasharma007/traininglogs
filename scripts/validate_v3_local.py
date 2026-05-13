"""Full value comparison: validation DB (v3 schema) vs local mirror (v2 schema).

Joins on session_id (deterministic — same input files produce same IDs).
Compares every session, exercise, working_set, and warmup_set row.

Expected diffs (not failures):
  - exercises.exercise_type: present in v2, absent in v3
  - exercises.tags / modality / movement_pattern: absent in v2, NULL in v3
  - working_sets.set_type: present in v2, absent in v3
  - warmups / cooldowns tables: exist in v3 only, must be empty

Any other value mismatch is a failure.

Usage:
  REGEN_DATABASE_URL=... LOCAL_DATABASE_URL=... .venv/bin/python scripts/validate_v3_local.py
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from traininglogs.db.db import get_connection

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"

SESSION_COMPARE_COLS = [
    "session_id", "date", "program", "program_author", "program_length_weeks",
    "phase", "week", "is_deload_week", "focus", "duration_minutes",
    "weight_unit", "user_id", "user_name", "source_file",
]

EXERCISE_COMPARE_COLS = [
    "number", "name", "notes", "warmup_notes", "form_cues",
    "goal_weight_kg", "goal_sets", "goal_rep_min", "goal_rep_max",
    "goal_rest_min", "goal_rest_seconds", "goal_distance_meters",
    "goal_target_duration_sec", "target_muscle_groups", "rep_tempo",
]

WORKING_SET_COMPARE_COLS = [
    "number", "weight_kg", "reps_full", "reps_partial",
    "left_reps_full", "left_reps_partial", "right_reps_full", "right_reps_partial",
    "rpe", "rep_quality", "rest_minutes", "rest_seconds",
    "duration_seconds", "distance_meters", "heart_rate_bpm",
    "failure_technique", "notes",
]


def _fetch_all(conn, query: str, params=None) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(query, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def main() -> int:
    val_url = os.environ.get("REGEN_DATABASE_URL", "")
    mirror_url = os.environ.get("LOCAL_DATABASE_URL", "")

    if not val_url:
        print("ERROR: REGEN_DATABASE_URL is not set.")
        return 1
    if not mirror_url:
        print("ERROR: LOCAL_DATABASE_URL is not set.")
        return 1

    val_conn = get_connection(val_url)
    mirror_conn = get_connection(mirror_url)

    failures = 0
    session_mismatches = 0
    exercise_mismatches = 0
    ws_mismatches = 0
    warmup_set_mismatches = 0

    # ── Sessions ──────────────────────────────────────────────────────────────
    print("=== Session-level comparison ===")
    val_sessions = {
        r["session_id"]: r
        for r in _fetch_all(val_conn, f"SELECT {', '.join(SESSION_COMPARE_COLS)} FROM sessions")
    }
    mirror_sessions = {
        r["session_id"]: r
        for r in _fetch_all(mirror_conn, f"SELECT {', '.join(SESSION_COMPARE_COLS)} FROM sessions")
    }

    only_val = set(val_sessions) - set(mirror_sessions)
    only_mirror = set(mirror_sessions) - set(val_sessions)
    if only_val:
        print(f"  {FAIL} sessions only in validation DB: {sorted(only_val)}")
        failures += len(only_val)
    if only_mirror:
        print(f"  {FAIL} sessions only in local mirror: {sorted(only_mirror)}")
        failures += len(only_mirror)

    common_sessions = set(val_sessions) & set(mirror_sessions)
    for sid in sorted(common_sessions):
        v, m = val_sessions[sid], mirror_sessions[sid]
        diffs = [col for col in SESSION_COMPARE_COLS if v.get(col) != m.get(col)]
        if diffs:
            for col in diffs:
                print(f"  {FAIL} {sid} sessions.{col}: val={v.get(col)!r}  mirror={m.get(col)!r}")
            failures += len(diffs)
            session_mismatches += 1

    if not only_val and not only_mirror and session_mismatches == 0:
        print(f"  {PASS} all {len(common_sessions)} sessions match")

    # ── Exercises ─────────────────────────────────────────────────────────────
    print("\n=== Exercise-level comparison ===")
    val_exercises = _fetch_all(
        val_conn,
        f"SELECT id, session_id, {', '.join(EXERCISE_COMPARE_COLS)} FROM exercises ORDER BY session_id, number",
    )
    mirror_exercises = _fetch_all(
        mirror_conn,
        f"SELECT id, session_id, {', '.join(EXERCISE_COMPARE_COLS)} FROM exercises ORDER BY session_id, number",
    )

    val_ex_map = {(r["session_id"], r["number"]): r for r in val_exercises}
    mirror_ex_map = {(r["session_id"], r["number"]): r for r in mirror_exercises}

    only_val_ex = set(val_ex_map) - set(mirror_ex_map)
    only_mirror_ex = set(mirror_ex_map) - set(val_ex_map)
    if only_val_ex:
        print(f"  {FAIL} exercises only in validation DB: {sorted(only_val_ex)[:5]}{'...' if len(only_val_ex) > 5 else ''}")
        failures += len(only_val_ex)
    if only_mirror_ex:
        print(f"  {FAIL} exercises only in local mirror: {sorted(only_mirror_ex)[:5]}{'...' if len(only_mirror_ex) > 5 else ''}")
        failures += len(only_mirror_ex)

    ex_id_map: dict[tuple, int] = {}  # (session_id, number) -> validation DB exercise id
    for key in sorted(set(val_ex_map) & set(mirror_ex_map)):
        v, m = val_ex_map[key], mirror_ex_map[key]
        ex_id_map[key] = v["id"]
        diffs = [col for col in EXERCISE_COMPARE_COLS if v.get(col) != m.get(col)]
        if diffs:
            for col in diffs:
                print(f"  {FAIL} {key[0]} ex#{key[1]} exercises.{col}: val={v.get(col)!r}  mirror={m.get(col)!r}")
            failures += len(diffs)
            exercise_mismatches += 1

    if not only_val_ex and not only_mirror_ex and exercise_mismatches == 0:
        print(f"  {PASS} all {len(val_ex_map)} exercises match")

    # ── Working sets ──────────────────────────────────────────────────────────
    print("\n=== Working-set comparison ===")

    # Build (session_id, ex_number, set_number) → row maps
    val_ws_raw = _fetch_all(
        val_conn,
        f"SELECT ws.exercise_id, e.session_id, e.number AS ex_number, {', '.join('ws.' + c for c in WORKING_SET_COMPARE_COLS)} "
        f"FROM working_sets ws JOIN exercises e ON ws.exercise_id = e.id",
    )
    mirror_ws_raw = _fetch_all(
        mirror_conn,
        f"SELECT ws.exercise_id, e.session_id, e.number AS ex_number, {', '.join('ws.' + c for c in WORKING_SET_COMPARE_COLS)} "
        f"FROM working_sets ws JOIN exercises e ON ws.exercise_id = e.id",
    )

    val_ws = {(r["session_id"], r["ex_number"], r["number"]): r for r in val_ws_raw}
    mirror_ws = {(r["session_id"], r["ex_number"], r["number"]): r for r in mirror_ws_raw}

    only_val_ws = set(val_ws) - set(mirror_ws)
    only_mirror_ws = set(mirror_ws) - set(val_ws)
    if only_val_ws:
        print(f"  {FAIL} working_sets only in validation DB: {sorted(only_val_ws)[:5]}{'...' if len(only_val_ws) > 5 else ''}")
        failures += len(only_val_ws)
    if only_mirror_ws:
        print(f"  {FAIL} working_sets only in local mirror: {sorted(only_mirror_ws)[:5]}{'...' if len(only_mirror_ws) > 5 else ''}")
        failures += len(only_mirror_ws)

    for key in sorted(set(val_ws) & set(mirror_ws)):
        v, m = val_ws[key], mirror_ws[key]
        diffs = [col for col in WORKING_SET_COMPARE_COLS if v.get(col) != m.get(col)]
        if diffs:
            for col in diffs:
                print(
                    f"  {FAIL} {key[0]} ex#{key[1]} set#{key[2]} working_sets.{col}: "
                    f"val={v.get(col)!r}  mirror={m.get(col)!r}"
                )
            failures += len(diffs)
            ws_mismatches += 1

    if not only_val_ws and not only_mirror_ws and ws_mismatches == 0:
        print(f"  {PASS} all {len(val_ws)} working_sets match")

    # ── Warmup sets ───────────────────────────────────────────────────────────
    print("\n=== Warmup-set comparison ===")
    WARMUP_SET_COLS = ["number", "weight_kg", "rep_count", "notes"]
    val_wus_raw = _fetch_all(
        val_conn,
        f"SELECT ws.exercise_id, e.session_id, e.number AS ex_number, {', '.join('ws.' + c for c in WARMUP_SET_COLS)} "
        f"FROM warmup_sets ws JOIN exercises e ON ws.exercise_id = e.id",
    )
    mirror_wus_raw = _fetch_all(
        mirror_conn,
        f"SELECT ws.exercise_id, e.session_id, e.number AS ex_number, {', '.join('ws.' + c for c in WARMUP_SET_COLS)} "
        f"FROM warmup_sets ws JOIN exercises e ON ws.exercise_id = e.id",
    )
    val_wus = {(r["session_id"], r["ex_number"], r["number"]): r for r in val_wus_raw}
    mirror_wus = {(r["session_id"], r["ex_number"], r["number"]): r for r in mirror_wus_raw}

    only_val_wus = set(val_wus) - set(mirror_wus)
    only_mirror_wus = set(mirror_wus) - set(val_wus)
    if only_val_wus:
        print(f"  {FAIL} warmup_sets only in validation DB: {sorted(only_val_wus)[:5]}")
        failures += len(only_val_wus)
    if only_mirror_wus:
        print(f"  {FAIL} warmup_sets only in local mirror: {sorted(only_mirror_wus)[:5]}")
        failures += len(only_mirror_wus)

    for key in sorted(set(val_wus) & set(mirror_wus)):
        v, m = val_wus[key], mirror_wus[key]
        diffs = [col for col in WARMUP_SET_COLS if v.get(col) != m.get(col)]
        if diffs:
            for col in diffs:
                print(
                    f"  {FAIL} {key[0]} ex#{key[1]} warmup#{key[2]} warmup_sets.{col}: "
                    f"val={v.get(col)!r}  mirror={m.get(col)!r}"
                )
            failures += len(diffs)
            warmup_set_mismatches += 1

    if not only_val_wus and not only_mirror_wus and warmup_set_mismatches == 0:
        print(f"  {PASS} all {len(val_wus)} warmup_sets match")

    # ── New v3 tables must be empty ───────────────────────────────────────────
    print("\n=== New v3 tables (warmups / cooldowns) ===")
    for table in ("warmups", "cooldowns"):
        with val_conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
        if count == 0:
            print(f"  {PASS} {table}: empty (rules parser produces no warmup/cooldown movements)")
        else:
            print(f"  {FAIL} {table}: {count} rows — unexpected, rules parser should not populate this")
            failures += count

    # ── Verify expected schema diffs ─────────────────────────────────────────
    print(f"\n=== Verifying expected schema diffs ===")

    # exercise_type: must exist in v2 mirror with non-null values; must not exist in v3
    with mirror_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM exercises WHERE exercise_type IS NOT NULL")
        mirror_et_count = cur.fetchone()[0]
    with val_conn.cursor() as cur:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='exercises' AND column_name='exercise_type'")
        val_has_et = cur.fetchone() is not None
    if mirror_et_count == len(val_exercises) and not val_has_et:
        print(f"  {PASS} exercises.exercise_type: {mirror_et_count} non-null rows in v2, column absent from v3")
    else:
        print(f"  {FAIL} exercises.exercise_type: mirror non-null={mirror_et_count} (expected {len(val_exercises)}), v3 has column={val_has_et}")
        failures += 1

    # set_type: must exist in v2 mirror with non-null values; must not exist in v3
    with mirror_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM working_sets WHERE set_type IS NOT NULL")
        mirror_st_count = cur.fetchone()[0]
    with val_conn.cursor() as cur:
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='working_sets' AND column_name='set_type'")
        val_has_st = cur.fetchone() is not None
    if mirror_st_count == len(val_ws) and not val_has_st:
        print(f"  {PASS} working_sets.set_type: {mirror_st_count} non-null rows in v2, column absent from v3")
    else:
        print(f"  {FAIL} working_sets.set_type: mirror non-null={mirror_st_count} (expected {len(val_ws)}), v3 has column={val_has_st}")
        failures += 1

    # tags / modality / movement_pattern: must exist in v3 as all-NULL; must not exist in v2
    for col in ("tags", "modality", "movement_pattern"):
        with val_conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM exercises WHERE {col} IS NOT NULL")
            val_non_null = cur.fetchone()[0]
        with mirror_conn.cursor() as cur:
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='exercises' AND column_name=%s", (col,))
            mirror_has_col = cur.fetchone() is not None
        if val_non_null == 0 and not mirror_has_col:
            print(f"  {PASS} exercises.{col}: all NULL in v3 (rules parser), column absent from v2")
        else:
            print(f"  {FAIL} exercises.{col}: v3 non-null={val_non_null} (expected 0), v2 has column={mirror_has_col}")
            failures += 1

    print(f"\n{'All checks passed.' if failures == 0 else f'{failures} check(s) FAILED.'}")

    val_conn.close()
    mirror_conn.close()
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
