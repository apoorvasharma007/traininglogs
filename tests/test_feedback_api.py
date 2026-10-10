"""POST /feedback: a feature request, bug report or other message from Settings."""
from __future__ import annotations

import os
from importlib.metadata import version

import pytest
from fastapi.testclient import TestClient

from traininglogs.db.db import apply_schema, get_connection
from signed_in import USER_A, auth, clean_test_data

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)
os.environ["DATABASE_URL"] = TEST_DB_URL
HEADERS = auth()


@pytest.fixture(scope="module")
def conn():
    c = get_connection(TEST_DB_URL)
    apply_schema(c)
    clean_test_data(c)
    yield c
    clean_test_data(c)
    c.close()


@pytest.fixture(scope="module")
def client(conn):
    from traininglogs.api.app import app

    with TestClient(app) as c:
        yield c


def test_saves_the_message_with_its_sender_and_the_app_version(client, conn) -> None:
    r = client.post("/feedback", headers=HEADERS, json={"kind": "feature", "message": "  A rest timer, please. "})
    assert r.status_code == 201
    with conn.cursor() as cur:
        cur.execute("SELECT user_id::text, kind, message, app_version FROM feedback WHERE id = %s", (r.json()["id"],))
        assert cur.fetchone() == (USER_A, "feature", "A rest timer, please.", version("traininglogs"))


@pytest.mark.parametrize("body", [
    {"kind": "feature", "message": "   "},
    {"kind": "praise", "message": "Nice app"},
    {"kind": "bug", "message": "x" * 2001},
])
def test_refuses_an_empty_message_an_unknown_kind_or_one_too_long(client, body) -> None:
    assert client.post("/feedback", headers=HEADERS, json=body).status_code == 422


def test_requires_sign_in(client) -> None:
    assert client.post("/feedback", json={"kind": "other", "message": "hi"}).status_code == 401
