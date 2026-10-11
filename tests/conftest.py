"""Every test signs its passes with the key in signed_in.py, and has users A and B in the test DB."""
from __future__ import annotations

import pytest

from signed_in import _KEY, TEST_DB_URL, USER_A, USER_A_AUTH, USER_B, USER_B_AUTH


@pytest.fixture(autouse=True)
def _passes_signed_by_the_test_key(monkeypatch):
    from traininglogs.api import auth as server_auth

    monkeypatch.setattr(server_auth, "_signing_key", lambda _token: _KEY.public_key())


@pytest.fixture(scope="session", autouse=True)
def _test_users():
    """Users A and B, with fixed ids, so tests can set owners on rows they insert directly, and
    the exercise library, loaded as scripts/load_exercise_library.py --apply would."""
    from traininglogs.db import library
    from traininglogs.db.db import apply_schema, get_connection

    conn = get_connection(TEST_DB_URL)
    apply_schema(conn)
    with conn.cursor() as cur:
        library.load_free_exercise_db(cur, library.read_free_exercise_db())
        library.load_library(cur, library.read_library())
        for user_id, auth_id in ((USER_A, USER_A_AUTH), (USER_B, USER_B_AUTH)):
            cur.execute(
                "INSERT INTO users (id, auth_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (user_id, auth_id)
            )
    conn.commit()
    conn.close()
