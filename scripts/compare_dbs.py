"""Exhaustive old-vs-new DB comparison.

Old DB (port 5432): pre-migration schema, old session ID format.
New DB (port 5434): new schema, path-based session IDs.

Join key: date (for sessions), date + exercise.number (for exercises),
          date + exercise.number + set.number (for working/warmup sets).

Exits 0 if all checks pass, 1 if any mismatch is found.
"""
import json
import sys
from decimal import Decimal

import psycopg2
import psycopg2.extras

OLD_DB = "postgresql://traininglogs:traininglogs@localhost:5432/traininglogs"
NEW_DB = "postgresql://traininglogs:traininglogs@localhost:5434/traininglogs_validation"

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

issues: list[str] = []


def connect(dsn: str):
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    return conn


def q(conn, sql: str, params=None) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def scalar(conn, sql: str, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()[0]


def _eq(a, b) -> bool:
    """Equality that handles Decimal/float and JSON/dict comparison."""
    if isinstance(a, Decimal):
        a = float(a)
    if isinstance(b, Decimal):
        b = float(b)
    if isinstance(a, str) and isinstance(b, str):
        try:
            aj, bj = json.loads(a), json.loads(b)
            return aj == bj
        except (json.JSONDecodeError, TypeError):
            pass
    if isinstance(a, dict) and isinstance(b, dict):
        return a == b
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) < 1e-6
    return a == b


def check(label: str, passed: bool, detail: str = "") -> None:
    tag = PASS if passed else FAIL
    print(f"  [{tag}] {label}" + (f": {detail}" if detail else ""))
    if not passed:
        issues.append(f"{label}: {detail}" if detail else label)


# ─────────────────────────────────────────────────────────────────────────────
# Section 1: Row counts
# ─────────────────────────────────────────────────────────────────────────────

def check_counts(old, new) -> None:
    print("\n── Row counts ──────────────────────────────────────────────────")
    for tbl in ("sessions", "exercises", "working_sets", "warmup_sets"):
        old_n = scalar(old, f"SELECT COUNT(*) FROM {tbl}")
        new_n = scalar(new, f"SELECT COUNT(*) FROM {tbl}")
        check(f"{tbl}: {old_n} old vs {new_n} new", old_n == new_n)


# ─────────────────────────────────────────────────────────────────────────────
# Section 2: Sessions — shared columns, joined by date
# ─────────────────────────────────────────────────────────────────────────────

SESSION_COLS = [
    "program", "program_author", "program_length_weeks",
    "phase", "week", "is_deload_week", "focus",
    "duration_minutes", "user_name", "user_id",
]


def _session_key(r: dict) -> tuple:
    """(date, focus) — unique per session even when two sessions share a date."""
    return (r["date"], r.get("focus") or "")


def check_sessions(old, new) -> None:
    print("\n── Sessions (shared columns, joined by date+focus) ─────────────")

    old_rows = {_session_key(r): r for r in q(old, "SELECT * FROM sessions ORDER BY date")}
    new_rows = {_session_key(r): r for r in q(new, "SELECT * FROM sessions ORDER BY date")}

    only_old = set(old_rows) - set(new_rows)
    only_new = set(new_rows) - set(old_rows)
    check("All sessions present in both DBs", not only_old and not only_new,
          f"only-old: {sorted(only_old)}, only-new: {sorted(only_new)}")

    mismatches = 0
    for key in sorted(set(old_rows) & set(new_rows)):
        o, n = old_rows[key], new_rows[key]
        for col in SESSION_COLS:
            if not _eq(o.get(col), n.get(col)):
                mismatches += 1
                issues.append(
                    f"sessions date={key[0]} focus={key[1]} col={col}: "
                    f"old={o.get(col)!r} new={n.get(col)!r}"
                )

    matched = len(set(old_rows) & set(new_rows))
    check(f"sessions field values ({matched} sessions × {len(SESSION_COLS)} cols)",
          mismatches == 0,
          f"{mismatches} mismatches" if mismatches else "")

    unpop = scalar(new,
        "SELECT COUNT(*) FROM sessions WHERE weight_unit IS NULL OR weight_unit = ''")
    check("sessions.weight_unit populated in all new rows", unpop == 0,
          f"{unpop} NULL/empty rows" if unpop else "")


# ─────────────────────────────────────────────────────────────────────────────
# Section 3: Exercises — shared columns, joined by date + exercise.number
# ─────────────────────────────────────────────────────────────────────────────

EXERCISE_COLS = [
    "name", "notes", "warmup_notes", "goal_weight_kg",
    "goal_sets", "goal_rep_min", "goal_rep_max", "goal_rest_min",
    "target_muscle_groups", "rep_tempo",
]

# form_cues is a text[] — compared separately
EXERCISE_ARRAY_COLS = ["form_cues", "target_muscle_groups"]


def check_exercises(old, new) -> None:
    print("\n── Exercises (shared columns, joined by date+focus+ex#) ────────")

    old_rows = q(old, """
        SELECT s.date, COALESCE(s.focus, '') AS focus, e.*
        FROM exercises e
        JOIN sessions s ON s.session_id = e.session_id
        ORDER BY s.date, s.focus, e.number
    """)
    new_rows = q(new, """
        SELECT s.date, COALESCE(s.focus, '') AS focus, e.*
        FROM exercises e
        JOIN sessions s ON s.session_id = e.session_id
        ORDER BY s.date, s.focus, e.number
    """)

    old_idx = {(r["date"], r["focus"], r["number"]): r for r in old_rows}
    new_idx = {(r["date"], r["focus"], r["number"]): r for r in new_rows}

    only_old = set(old_idx) - set(new_idx)
    only_new = set(new_idx) - set(old_idx)
    check("All (date, focus, ex#) keys present in both DBs",
          not only_old and not only_new,
          f"only-old: {len(only_old)}, only-new: {len(only_new)}")

    mismatches = 0
    for key in sorted(set(old_idx) & set(new_idx)):
        o, n = old_idx[key], new_idx[key]
        all_cols = EXERCISE_COLS + EXERCISE_ARRAY_COLS
        for col in all_cols:
            ov, nv = o.get(col), n.get(col)
            if isinstance(ov, list):
                ov = sorted(ov) if ov else []
            if isinstance(nv, list):
                nv = sorted(nv) if nv else []
            if not _eq(ov, nv):
                mismatches += 1
                issues.append(
                    f"exercises date={key[0]} focus={key[1]} ex#={key[2]} col={col}: "
                    f"old={ov!r} new={nv!r}"
                )

    matched = len(set(old_idx) & set(new_idx))
    check(f"exercises field values ({matched} exercises × {len(EXERCISE_COLS + EXERCISE_ARRAY_COLS)} cols)",
          mismatches == 0,
          f"{mismatches} mismatches" if mismatches else "")

    unpop = scalar(new, "SELECT COUNT(*) FROM exercises WHERE exercise_type IS NULL")
    check("exercises.exercise_type populated in all new rows", unpop == 0,
          f"{unpop} NULL rows" if unpop else "")


# ─────────────────────────────────────────────────────────────────────────────
# Section 4: Working sets — shared columns, joined by date + ex# + set#
# ─────────────────────────────────────────────────────────────────────────────

WORKING_SET_COLS = [
    "weight_kg", "reps_full", "reps_partial",
    "rpe", "rep_quality", "rest_minutes", "notes", "failure_technique",
]


def check_working_sets(old, new) -> None:
    print("\n── Working sets (shared columns, joined by date+focus+ex#+set#) ")

    old_rows = q(old, """
        SELECT s.date, COALESCE(s.focus, '') AS focus, e.number AS ex_num, ws.*
        FROM working_sets ws
        JOIN exercises e ON e.id = ws.exercise_id
        JOIN sessions s ON s.session_id = e.session_id
        ORDER BY s.date, s.focus, e.number, ws.number
    """)
    new_rows = q(new, """
        SELECT s.date, COALESCE(s.focus, '') AS focus, e.number AS ex_num, ws.*
        FROM working_sets ws
        JOIN exercises e ON e.id = ws.exercise_id
        JOIN sessions s ON s.session_id = e.session_id
        ORDER BY s.date, s.focus, e.number, ws.number
    """)

    old_idx = {(r["date"], r["focus"], r["ex_num"], r["number"]): r for r in old_rows}
    new_idx = {(r["date"], r["focus"], r["ex_num"], r["number"]): r for r in new_rows}

    only_old = set(old_idx) - set(new_idx)
    only_new = set(new_idx) - set(old_idx)
    check("All (date, focus, ex#, set#) keys present in both DBs",
          not only_old and not only_new,
          f"only-old: {len(only_old)}, only-new: {len(only_new)}")

    mismatches = 0
    for key in sorted(set(old_idx) & set(new_idx)):
        o, n = old_idx[key], new_idx[key]
        for col in WORKING_SET_COLS:
            ov, nv = o.get(col), n.get(col)
            if not _eq(ov, nv):
                mismatches += 1
                issues.append(
                    f"working_sets date={key[0]} focus={key[1]} ex#={key[2]} set#={key[3]} col={col}: "
                    f"old={ov!r} new={nv!r}"
                )

    matched = len(set(old_idx) & set(new_idx))
    check(f"working_sets field values ({matched} sets × {len(WORKING_SET_COLS)} cols)",
          mismatches == 0,
          f"{mismatches} mismatches" if mismatches else "")

    # New-column population checks
    for col in ("set_type",):
        unpop = scalar(new, f"SELECT COUNT(*) FROM working_sets WHERE {col} IS NULL")
        check(f"working_sets.{col} populated in all new rows", unpop == 0,
              f"{unpop} NULL rows" if unpop else "")


# ─────────────────────────────────────────────────────────────────────────────
# Section 5: Warmup sets — all shared columns, joined by date + ex# + warmup#
# ─────────────────────────────────────────────────────────────────────────────

WARMUP_SET_COLS = ["weight_kg", "rep_count", "notes"]


def check_warmup_sets(old, new) -> None:
    print("\n── Warmup sets (all columns, joined by date+focus+ex#+warmup#) ─")

    old_rows = q(old, """
        SELECT s.date, COALESCE(s.focus, '') AS focus, e.number AS ex_num, ws.*
        FROM warmup_sets ws
        JOIN exercises e ON e.id = ws.exercise_id
        JOIN sessions s ON s.session_id = e.session_id
        ORDER BY s.date, s.focus, e.number, ws.number
    """)
    new_rows = q(new, """
        SELECT s.date, COALESCE(s.focus, '') AS focus, e.number AS ex_num, ws.*
        FROM warmup_sets ws
        JOIN exercises e ON e.id = ws.exercise_id
        JOIN sessions s ON s.session_id = e.session_id
        ORDER BY s.date, s.focus, e.number, ws.number
    """)

    old_idx = {(r["date"], r["focus"], r["ex_num"], r["number"]): r for r in old_rows}
    new_idx = {(r["date"], r["focus"], r["ex_num"], r["number"]): r for r in new_rows}

    only_old = set(old_idx) - set(new_idx)
    only_new = set(new_idx) - set(old_idx)
    check("All (date, focus, ex#, warmup#) keys present in both DBs",
          not only_old and not only_new,
          f"only-old: {len(only_old)}, only-new: {len(only_new)}")

    mismatches = 0
    for key in sorted(set(old_idx) & set(new_idx)):
        o, n = old_idx[key], new_idx[key]
        for col in WARMUP_SET_COLS:
            ov, nv = o.get(col), n.get(col)
            if not _eq(ov, nv):
                mismatches += 1
                issues.append(
                    f"warmup_sets date={key[0]} focus={key[1]} ex#={key[2]} warmup#={key[3]} col={col}: "
                    f"old={ov!r} new={nv!r}"
                )

    matched = len(set(old_idx) & set(new_idx))
    check(f"warmup_sets field values ({matched} warmup sets × {len(WARMUP_SET_COLS)} cols)",
          mismatches == 0,
          f"{mismatches} mismatches" if mismatches else "")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"OLD DB: {OLD_DB}")
    print(f"NEW DB: {NEW_DB}")

    old = connect(OLD_DB)
    new = connect(NEW_DB)

    try:
        check_counts(old, new)
        check_sessions(old, new)
        check_exercises(old, new)
        check_working_sets(old, new)
        check_warmup_sets(old, new)
    finally:
        old.close()
        new.close()

    print("\n" + "─" * 65)
    if issues:
        print(f"[{FAIL}] {len(issues)} issue(s) found:\n")
        for i in issues:
            print(f"  • {i}")
        sys.exit(1)
    else:
        print(f"[{PASS}] All checks passed. Safe to cut over.")
        sys.exit(0)


if __name__ == "__main__":
    main()
