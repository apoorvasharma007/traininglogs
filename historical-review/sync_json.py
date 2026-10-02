"""Bring output_training_logs_json/bodybuilding_transformation_system/ in line with prod after the
review's batches. Fills only what the JSON has empty and prod has -- the same rule the batches
used -- and validates every file as a TrainingSession before writing it. The older uppercase
copy is left alone.

    .venv/bin/python historical-review/sync_json.py            # dry run
    .venv/bin/python historical-review/sync_json.py --write
"""
from __future__ import annotations

import glob
import json
import os
import sys

import psycopg2
from dotenv import load_dotenv

from traininglogs.models.models import TrainingSession

load_dotenv()

JSON_DIR = "output_training_logs_json/bodybuilding_transformation_system"


def num(x):
    return None if x is None else float(x)


def main() -> None:
    write = "--write" in sys.argv
    paths = {os.path.basename(p)[:-5]: p for p in glob.glob(f"{JSON_DIR}/**/*.json", recursive=True)}
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.set_session(readonly=True)
    cur = conn.cursor()
    cur.execute("SELECT session_id FROM sessions WHERE extraction_id IS NULL ORDER BY date")
    changed_files = changes = 0

    for (sid,) in cur.fetchall():
        path = paths[sid]
        data = json.load(open(path))
        before = json.dumps(data, sort_keys=True)
        cur.execute("SELECT id, number FROM exercises WHERE session_id = %s ORDER BY number", (sid,))
        db_ex = dict((n, i) for i, n in cur.fetchall())

        for ex in data["exercises"]:
            ex_id = db_ex[ex["number"]]
            cur.execute("SELECT number, weight_kg, rep_count, notes FROM warmup_sets "
                        "WHERE exercise_id = %s ORDER BY number", (ex_id,))
            warmups = cur.fetchall()
            if not ex.get("warmup_sets") and warmups:
                ex["warmup_sets"] = [{"number": n, "weight_kg": num(w), "rep_count": r, "notes": note}
                                     for n, w, r, note in warmups]
                changes += len(warmups)

            cur.execute("SELECT number, weight_kg, reps_full, reps_partial, rpe, rep_quality, notes "
                        "FROM working_sets WHERE exercise_id = %s ORDER BY number", (ex_id,))
            db_sets = cur.fetchall()
            if not ex.get("sets") and db_sets:
                ex["sets"] = [{"number": n, "weight_kg": num(w),
                               "rep_count": {"full": full, "partial": partial or 0},
                               "rpe": num(rpe), "rep_quality_assessment": q, "notes": note}
                              for n, w, full, partial, rpe, q, note in db_sets]
                changes += len(db_sets)
                continue
            by_number = {row[0]: row for row in db_sets}
            for s in ex.get("sets") or []:
                row = by_number.get(s["number"])
                if row is None:
                    continue
                _, _, _, _, rpe, quality, note = row
                if s.get("rpe") is None and rpe is not None:
                    s["rpe"] = num(rpe)
                    changes += 1
                if s.get("rep_quality_assessment") is None and quality is not None:
                    s["rep_quality_assessment"] = quality
                    changes += 1
                if note is not None and (s.get("notes") is None or
                                         (s["notes"] != note and s["notes"].strip() == note)):
                    s["notes"] = note
                    changes += 1

        if json.dumps(data, sort_keys=True) != before:
            TrainingSession.model_validate(data)
            changed_files += 1
            if write:
                with open(path, "w") as f:
                    f.write(json.dumps(data, indent=2))

    print(f"{changes} values filled across {changed_files} files"
          f" ({'written' if write else 'dry run'}).")


if __name__ == "__main__":
    main()
