"""Convert a database from before accounts to the new design (db-redesign-plan.md).

Everything in it becomes one person's: the owner whose Supabase account id and email are given.
In one transaction:

1. The old tables move into a schema called `old` (three new tables share their names).
2. schema.sql builds the new tables.
3. Every row is copied across with a new id, links rebuilt through the old ids:
   - raw_inputs -> input_text (an app session's id becomes its client_id);
   - the AI's readings of notes -> input_text_confirmation_cards (an app session's draft and the
     old repeat call's drafts aren't carried over: app sessions don't have cards now);
   - llm_calls -> ai_call_logs;
   - sessions -> workout_sessions (the old session id becomes the dedup key; a session imported
     from the markdown logs gets an `import` input holding it as it was stored);
   - exercises, working and warm-up sets, warm-ups, cool-downs, programs and their workouts;
   - every distinct exercise name -> one of the owner's user_exercises.
4. Counts are compared, old against new; any difference rolls everything back.
5. Without --commit it rolls back anyway: a dry run that changes nothing. With --commit, the old
   schema is dropped and it all commits.

    DATABASE_URL=... .venv/bin/python scripts/migrate_to_accounts.py --auth-id <uuid> --email <email>
    DATABASE_URL=... .venv/bin/python scripts/migrate_to_accounts.py --auth-id <uuid> --email <email> --commit

Take a backup first. Production only with Apoorva's approval in the same session.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg2
from psycopg2.extras import execute_values

from traininglogs.db.db import apply_schema
from traininglogs.db.ids import new_id
from traininglogs.db.insert import content_checksum, name_key

OLD_TABLES = (
    "raw_inputs", "extractions", "llm_calls", "sessions", "warmups", "cooldowns", "exercises",
    "working_sets", "warmup_sets", "programs", "program_workouts", "program_workout_exercises",
    "exercise_pins",
)


def _rows(cur, sql: str) -> list[dict]:
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _json(value):
    return json.dumps(value) if value is not None else None


def migrate(conn, auth_id: str, email: str) -> dict[str, tuple[int, int]]:
    """Runs steps 1 to 4 on `conn` without committing; returns {what: (old count, new count)}."""
    cur = conn.cursor()
    cur.execute("CREATE SCHEMA old")
    for table in OLD_TABLES:
        cur.execute(f"ALTER TABLE IF EXISTS public.{table} SET SCHEMA old")
    apply_schema(conn, commit=False)

    owner = new_id()
    cur.execute(
        "INSERT INTO users (id, auth_id, email, last_seen_at) VALUES (%s, %s, %s, now())", (owner, auth_id, email)
    )
    cur.execute("INSERT INTO profiles (user_id) VALUES (%s)", (owner,))

    raw = _rows(cur, "SELECT * FROM old.raw_inputs")
    drafts = _rows(cur, "SELECT * FROM old.extractions")
    sessions = _rows(cur, "SELECT * FROM old.sessions")
    raw_by_id = {r["id"]: r for r in raw}
    draft_by_id = {d["id"]: d for d in drafts}
    # An app session's raw input had its phone id as its own id and no source; a repeat's had the
    # repeated session as its source.
    app_inputs = {r["id"] for r in raw if r["source_kind"] == "manual" and r["source_file"] is None}

    # input_text
    input_id = {r["id"]: new_id() for r in raw}
    execute_values(cur, """
        INSERT INTO input_text (id, user_id, content, kind, client_id, checksum, source, created_at) VALUES %s""",
        [(input_id[r["id"]], owner, r["content"], r["source_kind"], r["id"] if r["id"] in app_inputs else None,
          r["checksum"], r["source_file"], r["captured_at"]) for r in raw])

    # cards: only the AI's readings of notes
    cards = [d for d in drafts if raw_by_id[d["raw_input_id"]]["source_kind"] == "text"]
    card_id = {d["id"]: new_id() for d in cards}
    if cards:
        execute_values(cur, """
            INSERT INTO input_text_confirmation_cards (id, user_id, input_id, model, prompt_version, extract,
                uncertain_fields, warnings, status, corrections, created_at, confirmed_at) VALUES %s""",
            [(card_id[d["id"]], owner, input_id[d["raw_input_id"]], d["model"], d["prompt_version"],
              _json(d["extract"]), d["uncertain_fields"], d["warnings"], d["status"], _json(d["corrections"]),
              d["created_at"], d["confirmed_at"]) for d in cards])

    # ai_call_logs
    calls = _rows(cur, "SELECT * FROM old.llm_calls")
    if calls:
        execute_values(cur, """
            INSERT INTO ai_call_logs (id, user_id, input_id, step, model, attempts, input_tokens, output_tokens,
                cost_usd, ms, cached, failed, raw_payload, created_at) VALUES %s""",
            [(new_id(), owner, input_id[c["raw_input_id"]], c["step"], c["model"], c["attempts"],
              c["input_tokens"], c["output_tokens"], c["cost_usd"], c["ms"], c["cached"], c["failed"],
              _json(c["raw_payload"]), c["created_at"]) for c in calls])

    # user_exercises: one per distinct name, linked to the shared list when the name matches
    exercises = _rows(cur, "SELECT * FROM old.exercises")
    plan_exercises = _rows(cur, "SELECT * FROM old.program_workout_exercises")
    names: dict[str, str] = {}
    for e in exercises + plan_exercises:
        names.setdefault(name_key(e["name"]), " ".join(e["name"].split()))
    user_exercise = {key: new_id() for key in names}
    execute_values(cur, """
        INSERT INTO user_exercises (id, user_id, name, exercise_id)
        SELECT v.id::uuid, v.user_id::uuid, v.name,
               (SELECT x.id FROM exercises x WHERE lower(x.name) = v.key OR v.key = ANY(x.other_names) LIMIT 1)
        FROM (VALUES %s) AS v (id, user_id, name, key)""",
        [(user_exercise[k], owner, n, k) for k, n in names.items()])

    # programs and workouts
    programs = _rows(cur, "SELECT * FROM old.programs")
    program_id = {p["id"]: new_id() for p in programs}
    if programs:
        execute_values(cur, """
            INSERT INTO programs (id, user_id, name, deload_after_days, following, following_since, archived_at,
                created_at) VALUES %s""",
            [(program_id[p["id"]], owner, p["name"], p["deload_after_days"], p["following"], p["following_since"],
              p["archived_at"], p["created_at"]) for p in programs])
    workouts = _rows(cur, "SELECT * FROM old.program_workouts")
    workout_id = {w["id"]: new_id() for w in workouts}
    if workouts:
        execute_values(cur, """
            INSERT INTO program_workouts (id, user_id, program_id, position, name, warmup, cooldown, archived_at,
                created_at) VALUES %s""",
            [(workout_id[w["id"]], owner, program_id[w["program_id"]], w["position"], w["name"], _json(w["warmup"]),
              _json(w["cooldown"]), w["archived_at"], w["created_at"]) for w in workouts])
    if plan_exercises:
        execute_values(cur, """
            INSERT INTO program_workout_exercises (id, user_id, workout_id, position, user_exercise_id, name,
                warmup_sets, working_sets, target_reps, amrap, alternatives) VALUES %s""",
            [(new_id(), owner, workout_id[e["workout_id"]], e["position"], user_exercise[name_key(e["name"])],
              e["name"], e["warmup_sets"], e["working_sets"], e["target_reps"], e["amrap"], e["alternatives"])
             for e in plan_exercises])

    # workout_sessions: each with its input; a note's also with its card
    session_id = {s["session_id"]: new_id() for s in sessions}
    imports = []
    session_rows = []
    for s in sessions:
        draft = draft_by_id.get(s["extraction_id"])
        if draft is not None:
            from_input, from_card = input_id[draft["raw_input_id"]], card_id.get(draft["id"])
        else:
            from_input, from_card = new_id(), None
            stored = json.dumps({k: str(v) if v is not None else None for k, v in s.items()}, sort_keys=True)
            imports.append((from_input, owner, stored, "import", None, content_checksum(stored), s["source_file"],
                            s["created_at"]))
        session_rows.append((
            session_id[s["session_id"]], owner, s["date"], s["duration_minutes"], s["focus"], s["notes"],
            s["session_id"], from_input, from_card, workout_id.get(s["program_workout_id"]), s["program"],
            s["program_author"], s["program_length_weeks"], s["phase"], s["week"], s["is_deload_week"],
            s["weight_unit"], s["source_file"], s["created_at"],
        ))
    if imports:
        execute_values(cur, """
            INSERT INTO input_text (id, user_id, content, kind, client_id, checksum, source, created_at) VALUES %s""",
            imports)
    if session_rows:
        execute_values(cur, """
            INSERT INTO workout_sessions (id, user_id, date, duration_minutes, focus, notes, dedup_key, input_id,
                confirmation_card_id, program_workout_id, program, program_author, program_length_weeks, phase, week,
                is_deload_week, weight_unit, source, created_at) VALUES %s""",
            session_rows)

    for kind in ("warmups", "cooldowns"):
        movements = _rows(cur, f"SELECT * FROM old.{kind}")
        if movements:
            execute_values(cur, f"""
                INSERT INTO workout_session_{kind} (id, user_id, session_id, position, name, reps, duration_seconds,
                    notes) VALUES %s""",
                [(new_id(), owner, session_id[m["session_id"]], m["number"], m["name"], m["reps"],
                  m["duration_seconds"], m["notes"]) for m in movements])

    exercise_id = {e["id"]: new_id() for e in exercises}
    if exercises:
        execute_values(cur, """
            INSERT INTO workout_session_exercises (id, user_id, session_id, position, user_exercise_id, name, notes,
                warmup_notes, tags, modality, movement_pattern, form_cues, target_muscle_groups, rep_tempo,
                goal_weight_kg, goal_sets, goal_rep_min, goal_rep_max, goal_rest_min, goal_rest_seconds,
                goal_distance_meters, goal_target_duration_sec) VALUES %s""",
            [(exercise_id[e["id"]], owner, session_id[e["session_id"]], e["number"], user_exercise[name_key(e["name"])],
              e["name"], e["notes"], e["warmup_notes"], e["tags"], e["modality"], e["movement_pattern"], e["form_cues"],
              e["target_muscle_groups"], e["rep_tempo"], e["goal_weight_kg"], e["goal_sets"], e["goal_rep_min"],
              e["goal_rep_max"], e["goal_rest_min"], e["goal_rest_seconds"], e["goal_distance_meters"],
              e["goal_target_duration_sec"]) for e in exercises])

    working = _rows(cur, "SELECT * FROM old.working_sets")
    warmup = _rows(cur, "SELECT * FROM old.warmup_sets")
    set_rows = [
        (new_id(), owner, exercise_id[s["exercise_id"]], s["number"], "working", s["weight_kg"], s["reps_full"],
         s["reps_partial"], s["left_reps_full"], s["left_reps_partial"], s["right_reps_full"], s["right_reps_partial"],
         s["rpe"], s["rep_quality"], s["rest_minutes"], s["rest_seconds"], s["duration_seconds"], s["distance_meters"],
         s["heart_rate_bpm"], s["notes"], _json(s["failure_technique"])) for s in working
    ] + [
        (new_id(), owner, exercise_id[s["exercise_id"]], s["number"], "warmup", s["weight_kg"], s["rep_count"], None,
         None, None, None, None, None, None, None, None, None, None, None, s["notes"], None) for s in warmup
    ]
    if set_rows:
        execute_values(cur, """
            INSERT INTO workout_session_sets (id, user_id, exercise_id, position, kind, weight_kg, reps_full,
                reps_partial, left_reps_full, left_reps_partial, right_reps_full, right_reps_partial, rpe, rep_quality,
                rest_minutes, rest_seconds, duration_seconds, distance_meters, heart_rate_bpm, notes,
                failure_technique) VALUES %s""",
            set_rows)

    def count(sql: str) -> int:
        cur.execute(sql)
        return cur.fetchone()[0]

    totals = "SELECT coalesce(sum(coalesce(weight_kg, 0) * coalesce(reps_full, 0)), 0) FROM {}"
    return {
        "inputs (plus imports)": (len(raw) + len(imports), count("SELECT count(*) FROM input_text")),
        "confirmation cards": (len(cards), count("SELECT count(*) FROM input_text_confirmation_cards")),
        "ai calls": (len(calls), count("SELECT count(*) FROM ai_call_logs")),
        "sessions": (len(sessions), count("SELECT count(*) FROM workout_sessions")),
        "sessions linked to a workout": (count("SELECT count(*) FROM old.sessions WHERE program_workout_id IS NOT NULL"),
                                         count("SELECT count(*) FROM workout_sessions WHERE program_workout_id IS NOT NULL")),
        "exercises": (len(exercises), count("SELECT count(*) FROM workout_session_exercises")),
        "working sets": (len(working), count("SELECT count(*) FROM workout_session_sets WHERE kind = 'working'")),
        "warm-up sets": (len(warmup), count("SELECT count(*) FROM workout_session_sets WHERE kind = 'warmup'")),
        "working kg x reps": (count(totals.format("old.working_sets")),
                              count(totals.format("workout_session_sets WHERE kind = 'working'"))),
        "warm-ups": (count("SELECT count(*) FROM old.warmups"), count("SELECT count(*) FROM workout_session_warmups")),
        "cool-downs": (count("SELECT count(*) FROM old.cooldowns"), count("SELECT count(*) FROM workout_session_cooldowns")),
        "programs": (len(programs), count("SELECT count(*) FROM programs")),
        "workouts": (len(workouts), count("SELECT count(*) FROM program_workouts")),
        "planned exercises": (len(plan_exercises), count("SELECT count(*) FROM program_workout_exercises")),
        "own exercises (distinct names)": (len(names), count("SELECT count(*) FROM user_exercises")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--auth-id", required=True, help="the owner's Supabase account id in this environment")
    parser.add_argument("--email", required=True)
    parser.add_argument("--commit", action="store_true", help="keep the result; without it, a dry run")
    args = parser.parse_args()

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        counts = migrate(conn, args.auth_id, args.email)
        width = max(map(len, counts))
        for what, (old, new) in counts.items():
            print(f"{what:{width}}  {old:>8}  {new:>8}  {'ok' if old == new else 'DIFFERENT'}")
        if any(old != new for old, new in counts.values()):
            conn.rollback()
            print("Rolled back: the counts differ.")
            return 1
        if not args.commit:
            conn.rollback()
            print("Dry run: rolled back. Run with --commit to keep it.")
            return 0
        conn.cursor().execute("DROP SCHEMA old CASCADE")
        conn.commit()
        print("Committed.")
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
