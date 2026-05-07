"""Strict validation of a regen DB against the prod baseline.

Usage:
  .venv/bin/python scripts/validate_regen.py

Reads REGEN_DATABASE_URL (regen DB) and DATABASE_URL (prod baseline).
All counts must match exactly. Spot-checks 10 randomly selected input files.
Exits non-zero on any failure.
"""
import os
import random
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from traininglogs.db.db import get_connection
from traininglogs.parser.extract import TrainingMarkdownParser
from traininglogs.parser.parse import DeepTrainingParser

PROJECT_ROOT = Path(__file__).parent.parent
INPUTS_DIR = PROJECT_ROOT / "inputs"

PASS = "PASS"
FAIL = "FAIL"


def _counts(conn) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM sessions)     AS sessions,
                (SELECT COUNT(*) FROM exercises)    AS exercises,
                (SELECT COUNT(*) FROM working_sets) AS working_sets,
                (SELECT COUNT(*) FROM warmup_sets)  AS warmup_sets
            """
        )
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, cur.fetchone()))


def _regen_exercise_counts(conn, session_id: str) -> dict:
    """Return exercise count and per-exercise set/warmup counts from regen DB."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, number FROM exercises WHERE session_id = %s ORDER BY number",
            (session_id,),
        )
        exercises = cur.fetchall()

        result = {}
        for ex_id, ex_num in exercises:
            cur.execute(
                "SELECT COUNT(*) FROM working_sets WHERE exercise_id = %s", (ex_id,)
            )
            ws_count = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM warmup_sets WHERE exercise_id = %s", (ex_id,)
            )
            wm_count = cur.fetchone()[0]
            result[ex_num] = {"working_sets": ws_count, "warmup_sets": wm_count}
    return result


def _parse_file(md_path: Path) -> dict:
    """Parse a .md file and return exercise/set counts without hitting the DB."""
    md_text = md_path.read_text(encoding="utf-8")
    base = TrainingMarkdownParser(md_text)
    intermediate = base.parse()
    deep = DeepTrainingParser(intermediate)
    session_dict = deep.build_training_session()

    result = {}
    for ex in session_dict.get("exercises", []):
        ex_num = ex["number"]
        working = ex.get("sets", [])
        warmup = ex.get("warmup_sets", [])
        result[ex_num] = {
            "working_sets": len(working),
            "warmup_sets": len(warmup),
        }
    return result


def _compute_session_id(md_path: Path) -> str:
    from traininglogs.processor.processor import compute_session_id, INPUTS_DIR as PROC_INPUTS
    from traininglogs.parser.extract import TrainingMarkdownParser

    md_text = md_path.read_text(encoding="utf-8")
    intermediate = TrainingMarkdownParser(md_text).parse()
    date_str = intermediate["metadata"].get("date", "")
    return compute_session_id(md_path.resolve(), PROC_INPUTS, date_str)


def main() -> int:
    regen_url = os.environ.get("REGEN_DATABASE_URL", "")
    prod_url = os.environ.get("DATABASE_URL", "")

    if not regen_url:
        print("ERROR: REGEN_DATABASE_URL is not set.")
        return 1
    if not prod_url:
        print("ERROR: DATABASE_URL is not set.")
        return 1

    failures = 0

    # ── 1. Count comparison ──────────────────────────────────────────────────
    print("=== Count validation ===")
    prod_conn = get_connection(prod_url)
    regen_conn = get_connection(regen_url)

    prod_counts = _counts(prod_conn)
    regen_counts = _counts(regen_conn)

    for table, prod_val in prod_counts.items():
        regen_val = regen_counts[table]
        status = PASS if regen_val == prod_val else FAIL
        print(f"  [{status}] {table}: prod={prod_val}  regen={regen_val}")
        if status == FAIL:
            failures += 1

    # ── 2. Spot-check 10 random input files ─────────────────────────────────
    print("\n=== Spot-check (10 random files) ===")
    all_md = sorted(INPUTS_DIR.rglob("*.md"))
    sample = random.sample(all_md, min(10, len(all_md)))

    for md_path in sorted(sample):
        rel = md_path.relative_to(PROJECT_ROOT)
        session_id = _compute_session_id(md_path)

        # Check session exists in regen DB
        with regen_conn.cursor() as cur:
            cur.execute("SELECT 1 FROM sessions WHERE session_id = %s", (session_id,))
            exists = cur.fetchone() is not None

        if not exists:
            print(f"  [FAIL] {rel} — session_id {session_id!r} not found in regen DB")
            failures += 1
            continue

        # Parse file live and compare exercise/set counts
        try:
            parsed_counts = _parse_file(md_path)
        except Exception as e:
            print(f"  [FAIL] {rel} — parse error: {e}")
            failures += 1
            continue

        db_counts = _regen_exercise_counts(regen_conn, session_id)

        ex_match = set(parsed_counts) == set(db_counts)
        if not ex_match:
            print(
                f"  [FAIL] {rel} — exercise numbers differ: "
                f"parsed={sorted(parsed_counts)} db={sorted(db_counts)}"
            )
            failures += 1
            continue

        file_ok = True
        for ex_num, p in parsed_counts.items():
            d = db_counts[ex_num]
            if p["working_sets"] != d["working_sets"]:
                print(
                    f"  [FAIL] {rel} ex#{ex_num} — working_sets: "
                    f"parsed={p['working_sets']} db={d['working_sets']}"
                )
                failures += 1
                file_ok = False
            if p["warmup_sets"] != d["warmup_sets"]:
                print(
                    f"  [FAIL] {rel} ex#{ex_num} — warmup_sets: "
                    f"parsed={p['warmup_sets']} db={d['warmup_sets']}"
                )
                failures += 1
                file_ok = False

        if file_ok:
            print(f"  [PASS] {rel}  ({len(parsed_counts)} exercises)")

    prod_conn.close()
    regen_conn.close()

    print(f"\n{'All checks passed.' if failures == 0 else f'{failures} check(s) FAILED.'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
