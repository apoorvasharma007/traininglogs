"""Signing in: which passes the server accepts, and the user a first sign-in creates."""
from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from signed_in import TEST_DB_URL, USER_A, token
from traininglogs.api.auth import user_for
from traininglogs.db.db import get_connection


@pytest.fixture()
def client():
    from traininglogs.api.app import app

    with TestClient(app) as c:
        yield c


def _get(client, headers: dict):
    return client.get("/programs", headers=headers)


@pytest.mark.parametrize("headers", [
    {},
    {"Authorization": "Bearer"},
    {"Authorization": "Basic abc"},
    {"Authorization": "Bearer not-a-pass"},
    {"Authorization": f"Bearer {token(key=ec.generate_private_key(ec.SECP256R1()))}"},  # signed by someone else
    {"Authorization": f"Bearer {token(exp=int(time.time()) - 10)}"},                     # expired
    {"Authorization": f"Bearer {token(iss='https://other-project.supabase.co/auth/v1')}"},  # another project
    {"Authorization": f"Bearer {token(aud='anon')}"},                                    # not a signed-in user
    {"x-api-key": "the old key"},
], ids=["none", "empty", "not bearer", "garbage", "wrong key", "expired", "wrong project", "wrong audience", "old api key"])
def test_refused_passes_are_401(client, headers) -> None:
    r = _get(client, headers)
    assert r.status_code == 401
    assert r.json()["detail"] == "You're signed out. Sign in again."


def test_every_api_route_needs_a_pass(client) -> None:
    from traininglogs.api.app import app

    for route in app.routes:
        methods = getattr(route, "methods", set()) - {"HEAD"}
        if not methods or not route.path.startswith(("/sessions", "/exercises", "/progress", "/inputs",
                                                     "/extractions", "/programs", "/templates", "/workouts")):
            continue
        path = route.path.replace("{", "").replace("}", "")
        for method in methods:
            assert client.request(method, path).status_code == 401, f"{method} {route.path}"


def test_a_first_sign_in_adds_one_user_and_later_ones_find_it(client) -> None:
    auth_id = str(uuid.uuid4())
    headers = {"Authorization": f"Bearer {token(sub=auth_id)}"}
    assert _get(client, headers).status_code == 200
    assert _get(client, headers).status_code == 200
    conn = get_connection(TEST_DB_URL)
    with conn.cursor() as cur:
        cur.execute("SELECT count(*), max(email) FROM users WHERE auth_id = %s", (auth_id,))
        assert cur.fetchone() == (1, f"{auth_id[:1]}@example.com")
        cur.execute("DELETE FROM users WHERE auth_id = %s", (auth_id,))
    conn.commit()
    conn.close()


def test_two_first_requests_at_once_make_one_user() -> None:
    auth_id = str(uuid.uuid4())

    def sign_in(_):
        conn = get_connection(TEST_DB_URL)
        try:
            return user_for(conn, {"sub": auth_id})
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = set(pool.map(sign_in, range(8)))
    assert len(ids) == 1
    conn = get_connection(TEST_DB_URL)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM users WHERE auth_id = %s", (auth_id,))
    conn.commit()
    conn.close()


def test_a_known_account_maps_to_its_user() -> None:
    from signed_in import USER_A_AUTH

    conn = get_connection(TEST_DB_URL)
    assert user_for(conn, {"sub": USER_A_AUTH}) == USER_A
    conn.close()


def test_a_failure_to_fetch_supabases_keys_is_503_not_signed_out(client, monkeypatch) -> None:
    import jwt

    from traininglogs.api import auth as server_auth

    def unreachable(_token):
        raise jwt.PyJWKClientConnectionError("Fail to fetch data from the url")

    monkeypatch.setattr(server_auth, "_signing_key", unreachable)
    r = _get(client, {"Authorization": f"Bearer {token()}"})
    assert r.status_code == 503
    assert r.json()["detail"] == "Couldn't check your sign-in (503). Try again in a minute."
