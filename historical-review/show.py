"""Print a historical session's source markdown next to what prod holds for it. Read-only.

    .venv/bin/python historical-review/show.py <session_id | source_file substring>
"""
from __future__ import annotations

import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def fmt_set(s: dict) -> str:
    reps = "?"
    if s["reps_full"] is not None:
        reps = f"{s['reps_full']}" + (f"+{s['reps_partial']}" if s["reps_partial"] else "")
    elif s["left_reps_full"] is not None or s["right_reps_full"] is not None:
        reps = f"L{s['left_reps_full']}+{s['left_reps_partial'] or 0}/R{s['right_reps_full']}+{s['right_reps_partial'] or 0}"
    parts = [f"{s['number']}. {s['weight_kg']} x {reps}"]
    for k in ("rpe", "rep_quality", "rest_minutes", "rest_seconds", "duration_seconds",
              "distance_meters", "failure_technique", "notes"):
        if s.get(k) is not None:
            parts.append(f"{k}={s[k]}")
    return "  ".join(str(p) for p in parts)


def main() -> None:
    key = sys.argv[1]
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.set_session(readonly=True)
    cur = conn.cursor()
    cur.execute(
        "SELECT session_id, source_file, date, phase, week, is_deload_week, focus, "
        "duration_minutes, notes FROM sessions WHERE session_id = %s OR source_file LIKE %s",
        (key, f"%{key}%"),
    )
    rows = cur.fetchall()
    if len(rows) != 1:
        raise SystemExit(f"{len(rows)} sessions match {key!r}")
    sid, source, *header = rows[0]

    print(f"===== SOURCE {source}")
    print(open(source).read().rstrip())
    print(f"\n===== DB {sid}  date/phase/week/deload/focus/duration/notes = {header}")

    cur.execute(
        "SELECT id, number, name, notes, warmup_notes, form_cues, goal_weight_kg, goal_sets, "
        "goal_rep_min, goal_rep_max, goal_rest_min, goal_rest_seconds, rep_tempo "
        "FROM exercises WHERE session_id = %s ORDER BY number",
        (sid,),
    )
    cols = [d[0] for d in cur.description]
    for ex in [dict(zip(cols, r)) for r in cur.fetchall()]:
        goal = (f"{ex['goal_weight_kg']} kg x {ex['goal_sets']} x {ex['goal_rep_min']}-"
                f"{ex['goal_rep_max']} rest {ex['goal_rest_min']}m/{ex['goal_rest_seconds']}s")
        print(f"\n[ex {ex['number']} id={ex['id']}] {ex['name']} | goal {goal} | tempo {ex['rep_tempo']}")
        for k in ("warmup_notes", "notes", "form_cues"):
            if ex[k]:
                print(f"  {k}: {ex[k]}")
        cur.execute("SELECT number, weight_kg, rep_count, notes FROM warmup_sets "
                    "WHERE exercise_id = %s ORDER BY number", (ex["id"],))
        for n, w, r, note in cur.fetchall():
            print(f"  W{n}. {w} x {r}" + (f"  notes={note}" if note else ""))
        cur.execute("SELECT * FROM working_sets WHERE exercise_id = %s ORDER BY number", (ex["id"],))
        scols = [d[0] for d in cur.description]
        for s in cur.fetchall():
            print("  " + fmt_set(dict(zip(scols, s))))


if __name__ == "__main__":
    main()
