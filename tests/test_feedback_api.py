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


def test_posts_new_feedback_to_discord_with_mentions_off(client, monkeypatch) -> None:
    import traininglogs.alerts as alerts

    posted: list[dict] = []

    class Ok:
        def raise_for_status(self) -> None: ...

    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/webhook")
    monkeypatch.setenv("APP_ENVIRONMENT", "staging")
    monkeypatch.setattr(alerts.httpx, "post", lambda url, json, timeout: posted.append(json) or Ok())
    assert client.post("/feedback", headers=HEADERS, json={"kind": "bug", "message": "@everyone the timer froze"}).status_code == 201
    [sent] = posted
    assert sent["content"].startswith("[staging] **Problem** from ")
    assert sent["content"].endswith("@everyone the timer froze")
    assert sent["allowed_mentions"] == {"parse": []}


def test_feedback_is_saved_even_when_discord_fails(client, monkeypatch) -> None:
    import httpx

    import traininglogs.alerts as alerts

    def down(url, json, timeout):
        raise httpx.ConnectError("discord is down")

    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.example/webhook")
    monkeypatch.setattr(alerts.httpx, "post", down)
    assert client.post("/feedback", headers=HEADERS, json={"kind": "other", "message": "hello"}).status_code == 201
