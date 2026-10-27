"""Signed-in test users, shared by every test file. The tests sign their own passes with a key pair made here and the server is
pointed at its public half, so no test ever reaches Supabase. User A owns everything a test makes
unless it says otherwise; user B is the other person, for checking A's data stays A's."""
from __future__ import annotations

import os
import time

import jwt
from cryptography.hazmat.primitives.asymmetric import ec

SUPABASE_URL = "https://test-project.supabase.co"
os.environ["SUPABASE_URL"] = SUPABASE_URL
os.environ["SUPABASE_PUBLISHABLE_KEY"] = "sb_publishable_test"

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)
# The server under test always uses the test database, never one named in .env.
os.environ["DATABASE_URL"] = TEST_DB_URL

_KEY = ec.generate_private_key(ec.SECP256R1())

# (users.id, Supabase account id) for the two test people.
USER_A = "a0000000-0000-4000-8000-00000000000a"
USER_A_AUTH = "a0000000-0000-4000-8000-0000000000aa"
USER_B = "b0000000-0000-4000-8000-00000000000b"
USER_B_AUTH = "b0000000-0000-4000-8000-0000000000bb"


def token(sub: str = USER_A_AUTH, key=None, **claims) -> str:
    """A pass as Supabase would sign it; keyword arguments override its claims."""
    body = {
        "sub": sub,
        "aud": "authenticated",
        "iss": f"{SUPABASE_URL}/auth/v1",
        "exp": int(time.time()) + 3600,
        "email": f"{sub[:1]}@example.com",
        **claims,
    }
    return jwt.encode(body, key or _KEY, algorithm="ES256")


def auth(sub: str = USER_A_AUTH) -> dict:
    """Request headers signed in as `sub` (user A by default)."""
    return {"Authorization": f"Bearer {token(sub)}"}


def exercise_ref(conn, name: str, user: str = USER_A) -> dict:
    """The library exercise with exactly this name, else `user`'s custom exercise of that name,
    made the first time: how a test names an exercise, where the app sends the id of the one
    picked."""
    from traininglogs.db.ids import new_id

    with conn.cursor() as cur:
        cur.execute("SELECT id::text FROM library_exercises WHERE name = %s", (name,))
        row = cur.fetchone()
        if row:
            return {"library_exercise_id": row[0]}
        cur.execute(
            "INSERT INTO custom_exercises (id, user_id, name) VALUES (%s, %s, %s)"
            " ON CONFLICT (user_id, name_key) DO UPDATE SET name = custom_exercises.name RETURNING id::text",
            (new_id(), user, name),
        )
        ref = {"custom_exercise_id": cur.fetchone()[0]}
    conn.commit()
    return ref


def save_session(conn, session: dict, user: str = USER_A, text: str | None = None) -> str:
    """Save a session (a TrainingSession as a dict) for `user` the way the app does: its input,
    then the session. An exercise without an id is named by exercise_ref. Returns the new session
    id."""
    from traininglogs.db.insert import insert_input, insert_session
    from traininglogs.ingest.confirm import dedup_key
    from traininglogs.models.models import TrainingSession

    text = text or repr(session)
    exercises = [
        e if e.get("library_exercise_id") or e.get("custom_exercise_id") else {**e, **exercise_ref(conn, e["name"], user)}
        for e in session.get("exercises", [])
    ]
    model = TrainingSession.model_validate({
        "data_model_version": "0.0.1", "data_model_type": "TrainingSession", "user_id": "-",
        "user_name": "-", **session, "exercises": exercises, "session_id": dedup_key(text, str(session["date"])),
    })
    input_id = insert_input(conn, user, text, kind="manual")
    session_id = insert_session(conn, user, model, input_id)
    assert session_id is not None
    return session_id


def clean_test_data(conn) -> None:
    """Empty every table of people's data (the test database holds nothing else). Users A and B
    and the shared exercise list stay, with no key lifts pinned."""
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET key_lifts = NULL WHERE key_lifts IS NOT NULL")
        cur.execute(
            "TRUNCATE input_text, input_text_confirmation_cards, ai_call_logs, workout_sessions,"
            " workout_session_warmups, workout_session_cooldowns, workout_session_exercises,"
            " workout_session_sets, programs, program_workouts, program_workout_exercises,"
            " program_workout_exercise_alternatives, custom_exercises, feedback"
        )
    conn.commit()
