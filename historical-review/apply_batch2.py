"""Batch 2: sets written as prose. Approved by Apoorva 2026-10-03.

Warmups are converted only where the exercise has no warmup rows at all -- where it already has
some, the prose is a routine description or a duplicate, and converting it would double-count.
Every conversion below was read by hand: the prose is matched exactly, and the rows it becomes
are written out, not parsed. The prose itself stays in its notes field unchanged.

Not converted, by decision: goals ("55x12 perfect is the goal", "120x 15 perfect reps is
hypertrophic goal", "63kg for 8 reps", "10 kg added weight", "10 kg or 7.5 kg") and the
instruction "4.5 x feel ... If needed".

One working-set fix: the 2025-10-25 Seated DB Shoulder Press has no "### Working Sets"
section; its two sets were typed under "### Warmup Notes" and never stored.

    .venv/bin/python historical-review/apply_batch2.py            # dry run
    .venv/bin/python historical-review/apply_batch2.py --apply    # one transaction against prod
"""
from __future__ import annotations

import os
import sys

import psycopg2
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from check import parse_file  # noqa: E402

load_dotenv()

AROUND_EXTENDED = "around the world arms extended time under tension is good enough resistance"
AROUND_BENCH = ("around the world, lift ass off the bench or let the shoulders drop to extreme "
                "range of motion under load, keep breathing, rep count feeling based")
ROTATION = ("unilateral with rotation, massage the shoulder ball and socket joint by rotating "
            "elbows all around at bottom position, rep count feeling based")

# (exercise name, prose section, exact prose) -> warmup rows (weight_kg, reps or None, note)
CONVERSIONS: dict[tuple[str, str, str], list[tuple[float, int | None, str | None]]] = {
    ("DB Bulgarian Split Squat", "notes",
     "1. 20 x feel Can go heavier than 30 too but try with perfect technique"):
        [(20, None, None)],
    ("DB Bulgarian Split Squat", "notes",
     "1. 15 x feel 2. 17.5 x feel Can go heavier than 30 too but try with perfect technique"):
        [(15, None, None), (17.5, None, None)],
    ("DB Bulgarian Split Squat", "notes", "1. 15 x feel 2. 17.5 x feel Can go heavier"):
        [(15, None, None), (17.5, None, None)],
    ("Seated DB Shoulder Press", "warmup notes",
     "Don’t use heavy weights preserve strength for working sets and avoid injury risk 0 x feel - "
     + AROUND_EXTENDED + ". 2.5  x feel - " + AROUND_BENCH + ". 12.5 x  feel - " + ROTATION + "."):
        [(0, None, AROUND_EXTENDED), (2.5, None, AROUND_BENCH), (12.5, None, ROTATION)],
    ("Seated DB Shoulder Press", "warmup notes",
     "Don’t use heavy weights preserve strength for working sets and avoid injury risk. "
     "12.5 x  feel - " + ROTATION + "."):
        [(12.5, None, ROTATION)],
    ("Leg Press", "warmup notes", "Pyramid. 200 kgs power kicks."):
        [(200, None, "power kicks")],
    ("Pec Dec", "warmup notes",
     "1. pyramid warmup 2. 55 x 9 - one heavy warmup, at top position of squeeze take arm out "
     "and in to feel all the pecs, do one light warmup for resilience"):
        [(55, 9, "one heavy warmup, at top position of squeeze take arm out and in to feel all "
                 "the pecs, do one light warmup for resilience")],
    ("Walking Lunge", "notes",
     "1. 20 x feel Careful with knee fatigue. We need to fix them before we killshot here."):
        [(20, None, None)],
    ("Walking Lunge", "notes",
     "1. 17.5 x feel 2. 17.5 x feel Careful with knee fatigue. We need to fix them before we "
     "killshot here."):
        [(17.5, None, None), (17.5, None, None)],
    ("Leg Extension", "warmup notes",
     "Pyramid warmup using unilateral, partials and isometric. 36 x feel - unilateral.  43 x feel "
     "- unilateral.  50 x feel - unilateral but this weight hurt my knees and was hard"):
        [(36, None, "unilateral"), (43, None, "unilateral"),
         (50, None, "unilateral but this weight hurt my knees and was hard")],
    ("Pec Dec Single Arm", "warmup notes",
     "pyramid warmup. 32  x 10 - one light warmup, do heavier next time. 66 x 4 - one heavy "
     "warmup, at top position of squeeze take arm out and in to feel all the pecs."):
        [(32, 10, "one light warmup, do heavier next time"),
         (66, 4, "one heavy warmup, at top position of squeeze take arm out and in to feel all "
                 "the pecs")],
}

# Working sets typed under Warmup Notes: (source_file, exercise number) -> rows
# (weight_kg, reps_full, rpe, quality)
MISPLACED_WORKING_SETS = {
    ("inputs/programs/bodybuilding_transformation_system/phase_2/week_2/"
     "push_hypertrophy_foundation_block.md", 2):
        [(17.5, 13, 8.5, "perfect"), (17.5, 12, 10, "perfect")],
}


def norm(text: str) -> str:
    return " ".join(text.replace("\xa0", " ").split())


def main() -> None:
    apply = "--apply" in sys.argv
    conversions = {(n, k, norm(t)): rows for (n, k, t), rows in CONVERSIONS.items()}
    used: set[tuple[str, str, str]] = set()

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    counts_sql = ("SELECT (SELECT COUNT(*) FROM sessions),(SELECT COUNT(*) FROM exercises),"
                  "(SELECT COUNT(*) FROM working_sets),(SELECT COUNT(*) FROM warmup_sets)")
    cur.execute(counts_sql)
    before = cur.fetchone()

    log: list[str] = []
    n_warmups = n_working = 0
    cur.execute("SELECT session_id, source_file, date FROM sessions "
                "WHERE extraction_id IS NULL ORDER BY date")
    for sid, path, date in cur.fetchall():
        entries: list[str] = []
        cur.execute("SELECT e.id, e.number, e.name, "
                    "(SELECT COUNT(*) FROM warmup_sets w WHERE w.exercise_id = e.id), "
                    "(SELECT COUNT(*) FROM working_sets s WHERE s.exercise_id = e.id) "
                    "FROM exercises e WHERE session_id = %s ORDER BY number", (sid,))
        for src, (ex_id, n, name, n_warm, n_work) in zip(parse_file(path), cur.fetchall()):
            for kind, text in src.prose.items():
                key = (name.strip(), kind, norm(text))
                if key not in conversions:
                    continue
                used.add(key)
                if n_warm:
                    entries.append(f"- ex {n} {name}: skipped, already has {n_warm} warmup rows")
                    continue
                for i, (w, reps, note) in enumerate(conversions[key], start=1):
                    entries.append(f"- ex {n} {name}: **added warmup {i}** {w:g} kg × "
                                   f"{reps if reps is not None else 'feel'}"
                                   f"{f' — {note!r}' if note else ''}  ← {kind}")
                    if apply:
                        cur.execute("INSERT INTO warmup_sets (exercise_id, number, weight_kg, "
                                    "rep_count, notes) VALUES (%s, %s, %s, %s, %s)",
                                    (ex_id, i, w, reps, note))
                    n_warmups += 1
            for i, (w, reps, rpe, quality) in enumerate(
                MISPLACED_WORKING_SETS.get((path, n), []), start=1
            ):
                if n_work:
                    entries.append(f"- ex {n} {name}: skipped, already has {n_work} working sets")
                    break
                entries.append(f"- ex {n} {name}: **added working set {i}** {w:g} kg × {reps} "
                               f"RPE {rpe:g} {quality}  ← typed under Warmup Notes")
                if apply:
                    cur.execute("INSERT INTO working_sets (exercise_id, number, weight_kg, "
                                "reps_full, reps_partial, rpe, rep_quality) "
                                "VALUES (%s, %s, %s, %s, 0, %s, %s)",
                                (ex_id, i, w, reps, rpe, quality))
                n_working += 1
        if entries:
            log.append(f"\n### {date} · `{sid}` · {path.split('/', 2)[-1]}\n")
            log.extend(entries)

    unused = set(conversions) - used
    if unused:
        conn.rollback()
        raise SystemExit(f"conversions that matched no session (prose changed?): {unused}")

    cur.execute(counts_sql)
    after = cur.fetchone()
    expected = (before[0], before[1], before[2] + n_working, before[3] + n_warmups)
    if apply:
        if after != expected:
            conn.rollback()
            raise SystemExit(f"counts {after} != expected {expected}; rolled back")
        conn.commit()
    else:
        conn.rollback()

    print(f"## Batch 2 — sets written as prose ({'APPLIED' if apply else 'dry run'})\n")
    print(f"{n_warmups} warmup sets added, {n_working} working sets added. "
          f"Counts {before} → {after if apply else expected}.")
    print("\n".join(log))


if __name__ == "__main__":
    main()
