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

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)

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
