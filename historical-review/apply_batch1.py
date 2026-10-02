"""Batch 1: the mechanical misses -- set quality, RPE and notes the rules parser dropped, and
warmup sets under headings it didn't recognise. Only fills values prod has empty; a value prod
has that differs from the source is logged as a question, never overwritten.

    .venv/bin/python historical-review/apply_batch1.py            # dry run: prints the log
    .venv/bin/python historical-review/apply_batch1.py --apply    # one transaction against prod
"""
from __future__ import annotations

import os
import sys

import psycopg2
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))
from check import parse_file  # noqa: E402

load_dotenv()


def main() -> None:
    apply = "--apply" in sys.argv
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()
    counts_sql = ("SELECT (SELECT COUNT(*) FROM sessions),(SELECT COUNT(*) FROM exercises),"
                  "(SELECT COUNT(*) FROM working_sets),(SELECT COUNT(*) FROM warmup_sets)")
    cur.execute(counts_sql)
    before = cur.fetchone()

    log: list[str] = []
    questions: list[str] = []
    n_set_updates = n_warmups = 0

    cur.execute("SELECT session_id, source_file, date FROM sessions "
                "WHERE extraction_id IS NULL ORDER BY date")
    for sid, path, date in cur.fetchall():
        entries: list[str] = []
        cur.execute("SELECT id, number, name FROM exercises WHERE session_id = %s ORDER BY number",
                    (sid,))
        db_exercises = cur.fetchall()
        for src, (ex_id, ex_num, ex_name) in zip(parse_file(path), db_exercises):
            label = f"ex {ex_num} {ex_name}"

            # Warmup sets: only when prod has none for this exercise and the source lists some.
            cur.execute("SELECT COUNT(*) FROM warmup_sets WHERE exercise_id = %s", (ex_id,))
            if cur.fetchone()[0] == 0 and src.warmups:
                for w in src.warmups:
                    entries.append(f"- {label}: **added warmup {w.number}** {w.weight} kg × "
                                   f"{w.full if w.full is not None else 'feel'}"
                                   f"{f' — {w.note!r}' if w.note else ''}  ← `{w.raw}`")
                    if apply:
                        cur.execute(
                            "INSERT INTO warmup_sets (exercise_id, number, weight_kg, rep_count, notes) "
                            "VALUES (%s, %s, %s, %s, %s)",
                            (ex_id, w.number, w.weight, w.full, w.note),
                        )
                    n_warmups += 1

            cur.execute("SELECT id, number, rpe, rep_quality, notes FROM working_sets "
                        "WHERE exercise_id = %s ORDER BY number", (ex_id,))
            for s, (ws_id, n, rpe, quality, note) in zip(src.sets, cur.fetchall()):
                changes: dict[str, object] = {}
                if s.rpe is not None:
                    if rpe is None:
                        changes["rpe"] = s.rpe
                    elif float(rpe) != s.rpe:
                        questions.append(f"{sid} {label} set {n}: rpe prod {rpe} vs source {s.rpe}  ← `{s.raw}`")
                if s.quality is not None:
                    if quality is None:
                        changes["rep_quality"] = s.quality
                    elif quality != s.quality:
                        questions.append(f"{sid} {label} set {n}: quality prod {quality} vs source {s.quality}  ← `{s.raw}`")
                if s.note is not None:
                    if note is None or note.strip() == s.note and note != s.note:
                        changes["notes"] = s.note
                    elif note.strip() != s.note:
                        questions.append(f"{sid} {label} set {n}: note prod {note!r} vs source {s.note!r}")
                if changes:
                    old = {"rpe": rpe, "rep_quality": quality, "notes": note}
                    entries.append(f"- {label}, set {n}: " + ", ".join(
                        f"{k} {old[k]!r} → {v!r}" for k, v in changes.items()) + f"  ← `{s.raw}`")
                    if apply:
                        sets_sql = ", ".join(f"{k} = %s" for k in changes)
                        cur.execute(f"UPDATE working_sets SET {sets_sql} WHERE id = %s",
                                    (*changes.values(), ws_id))
                        assert cur.rowcount == 1
                    n_set_updates += 1
        if entries:
            log.append(f"\n### {date} · `{sid}` · {path.split('/', 2)[-1]}\n")
            log.extend(entries)

    cur.execute(counts_sql)
    after = cur.fetchone()
    expected = (before[0], before[1], before[2], before[3] + (n_warmups if apply else 0))
    summary = (f"{n_set_updates} working sets updated, {n_warmups} warmup sets added, "
               f"{len(questions)} questions. Counts {before} → {after}.")

    if apply:
        if after != expected:
            conn.rollback()
            raise SystemExit(f"counts {after} != expected {expected}; rolled back")
        conn.commit()
    else:
        conn.rollback()

    print(f"## Batch 1 — mechanical misses ({'APPLIED' if apply else 'dry run'})\n")
    print(summary)
    print("\n".join(log))
    if questions:
        print("\n### Questions (not changed)\n")
        print("\n".join(f"- {q}" for q in questions))


if __name__ == "__main__":
    main()
