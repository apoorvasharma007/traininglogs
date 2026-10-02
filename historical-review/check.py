"""Re-read every historical source file with a forgiving parser and list every place it
disagrees with prod. Read-only. Each finding is then judged by hand and logged in log.md.

    .venv/bin/python historical-review/check.py [source_file substring]
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field

import psycopg2
from dotenv import load_dotenv

load_dotenv()

NUM = r"\d+(?:\.\d+)?"
SET_LINE = re.compile(
    rf"^(?P<n>\d+)\.\s*(?P<w>{NUM})\s*(?:kgs?|lbs?)?\s*x\s*(?P<rest>.*)$", re.I
)
REPS = re.compile(r"^(?P<full>\d+)(?![\d.])(?:\s*\+\s*(?P<partial>\d+))?", re.I)
# The note starts at " - ", or at "- " straight after a number ("RPE 9.5- felt good").
NOTE_SPLIT = re.compile(r"\s+-\s*|(?<=\d)-\s+")
RPE = re.compile(rf"RPE\s*(?P<rpe>{NUM})", re.I)
QUALITY = re.compile(r"\b(perfect|good|bad|learning)\b", re.I)
FAILURE = re.compile(r"failure:\s*([a-z_]+)\s*\(([^)]*)\)", re.I)
WARMUP_HEADINGS = {"warmup", "warm up", "warmup sets"}
FAILURE_TYPES = {"llp": "LLP", "statichold": "StaticHold", "myo": "MyoReps", "dropset": "DropSet"}


@dataclass
class SetLine:
    number: int
    weight: float
    full: int | None
    partial: int
    rpe: float | None
    quality: str | None
    failure: str | None
    note: str | None
    raw: str


@dataclass
class Exercise:
    number: int
    name: str = ""
    warmups: list[SetLine] = field(default_factory=list)
    sets: list[SetLine] = field(default_factory=list)
    prose: dict[str, str] = field(default_factory=dict)
    unparsed: list[str] = field(default_factory=list)


def parse_set(line: str) -> SetLine | None:
    m = SET_LINE.match(line)
    if not m:
        return None
    rest = m.group("rest")
    body, note = (NOTE_SPLIT.split(rest, maxsplit=1) + [""])[:2]
    reps = REPS.match(body.strip())
    rpe = RPE.search(body)
    quality = QUALITY.search(RPE.sub("", FAILURE.sub("", body)))
    failure = FAILURE.search(body)
    return SetLine(
        number=int(m.group("n")),
        weight=float(m.group("w")),
        full=int(reps.group("full")) if reps else None,
        partial=int(reps.group("partial") or 0) if reps else 0,
        rpe=float(rpe.group("rpe")) if rpe else None,
        quality=quality.group(1).lower() if quality else None,
        failure=FAILURE_TYPES.get(failure.group(1).lower(), failure.group(1)) if failure else None,
        note=note.strip() or None,
        raw=line,
    )


def parse_file(path: str) -> list[Exercise]:
    exercises: list[Exercise] = []
    section = None
    for raw in open(path):
        line = raw.strip()
        if re.match(r"^##\s+Exercise\s+\d+", line):
            exercises.append(Exercise(number=int(re.findall(r"\d+", line)[0])))
            section = None
            continue
        if not exercises:
            continue
        ex = exercises[-1]
        if line.startswith("**Name:**"):
            ex.name = line.split("**Name:**", 1)[1].strip()
        elif line.startswith("### "):
            section = line[4:].strip().lower()
        elif section and line:
            if re.match(r"^\d+\.", line) and section in WARMUP_HEADINGS | {"working sets"}:
                parsed = parse_set(line)
                if parsed is None:
                    ex.unparsed.append(f"[{section}] {line}")
                elif section == "working sets":
                    ex.sets.append(parsed)
                else:
                    ex.warmups.append(parsed)
            elif section in ("warmup notes", "notes"):
                ex.prose[section] = (ex.prose.get(section, "") + " " + line).strip()
    return exercises


def db_session(cur, source: str) -> tuple[str, list[dict]]:
    cur.execute("SELECT session_id FROM sessions WHERE source_file = %s", (source,))
    sid = cur.fetchone()[0]
    cur.execute("SELECT id, number, name, notes, warmup_notes FROM exercises "
                "WHERE session_id = %s ORDER BY number", (sid,))
    exs = [dict(zip(("id", "number", "name", "notes", "warmup_notes"), r)) for r in cur.fetchall()]
    for ex in exs:
        cur.execute("SELECT number, weight_kg, rep_count, notes FROM warmup_sets "
                    "WHERE exercise_id = %s ORDER BY number", (ex["id"],))
        ex["warmups"] = cur.fetchall()
        cur.execute("SELECT number, weight_kg, reps_full, reps_partial, rpe, rep_quality, "
                    "failure_technique->>'technique_type', notes, left_reps_full "
                    "FROM working_sets WHERE exercise_id = %s ORDER BY number", (ex["id"],))
        ex["sets"] = cur.fetchall()
    return sid, exs


def f(x) -> float | None:
    return None if x is None else float(x)


def compare(path: str, cur) -> list[str]:
    findings: list[str] = []
    src = parse_file(path)
    sid, db = db_session(cur, path)
    if len(src) != len(db):
        findings.append(f"exercise count: source {len(src)} vs db {len(db)}")
    for s, d in zip(src, db):
        tag = f"ex{s.number} {s.name[:30]}"
        if s.name.strip() != d["name"].strip():
            findings.append(f"{tag}: name db={d['name']!r}")
        for u in s.unparsed:
            findings.append(f"{tag}: UNPARSED {u}")
        if len(s.warmups) != len(d["warmups"]):
            findings.append(f"{tag}: warmup count source {len(s.warmups)} vs db {len(d['warmups'])}"
                            f" | source: {[w.raw for w in s.warmups]}")
        else:
            for w, (n, dw, dr, dn) in zip(s.warmups, d["warmups"]):
                if f(dw) != w.weight or dr != w.full:
                    findings.append(f"{tag}: warmup {w.number} source {w.weight}x{w.full} vs db {dw}x{dr}")
        if len(s.sets) != len(d["sets"]):
            findings.append(f"{tag}: set count source {len(s.sets)} vs db {len(d['sets'])}")
        for w, row in zip(s.sets, d["sets"]):
            n, dw, full, partial, rpe, quality, failure, note, left = row
            diffs = []
            if f(dw) != w.weight:
                diffs.append(f"weight {dw}->{w.weight}")
            if left is None and (full, partial or 0) != (w.full, w.partial):
                diffs.append(f"reps {full}+{partial}->{w.full}+{w.partial}")
            if f(rpe) != w.rpe:
                diffs.append(f"rpe {rpe}->{w.rpe}")
            if quality != w.quality:
                diffs.append(f"quality {quality}->{w.quality}")
            if failure != w.failure:
                diffs.append(f"failure {failure}->{w.failure}")
            if (note or None) != w.note:
                diffs.append(f"note {note!r}->{w.note!r}")
            if diffs:
                findings.append(f"{tag}: set {w.number}: " + ", ".join(diffs) + f"   | {w.raw}")
        for key, text in s.prose.items():
            if re.search(rf"{NUM}\s*(?:kgs?|x|for|reps?)\b", text, re.I):
                findings.append(f"{tag}: PROSE [{key}] {text}")
    return [f"{sid}  {path}"] + findings if findings else []


def main() -> None:
    needle = sys.argv[1] if len(sys.argv) > 1 else ""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.set_session(readonly=True)
    cur = conn.cursor()
    cur.execute("SELECT source_file FROM sessions WHERE extraction_id IS NULL AND source_file LIKE %s "
                "ORDER BY date", (f"%{needle}%",))
    total = 0
    for (path,) in cur.fetchall():
        out = compare(path, cur)
        if out:
            total += len(out) - 1
            print("\n".join(out) + "\n")
    print(f"{total} findings")


if __name__ == "__main__":
    main()
