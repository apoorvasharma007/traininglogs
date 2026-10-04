"""Repeat a past session (roadmap Phase 5b Step 7): no LLM, against the real test DB.

The source session is inserted through the normal insert path and read back with
`get_session`, so the mapping is tested against what the tables actually hold -- not a
hand-written dict that could drift from it.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from traininglogs.db.db import apply_schema, get_connection
from traininglogs.db.fetch import get_extraction, get_raw_input, get_session
from traininglogs.db.insert import insert_session
from traininglogs.ingest.repeat import repeat_session, session_to_extract
from traininglogs.models.models import TrainingSession

from signed_in import USER_A, USER_B_AUTH, auth

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)
os.environ["DATABASE_URL"] = TEST_DB_URL

SOURCE_ID = "repeat-test-source-001"

SOURCE = {
    "data_model_version": "0.0.1",
    "data_model_type": "TrainingSession",
    "session_id": SOURCE_ID,
    "user_id": "7",
    "user_name": "Apoorva Sharma",
    "date": "2026-09-19",
    "program": "Test Program",
    "phase": 2,
    "week": 3,
    "is_deload_week": False,
    "focus": "Strength",
    "session_duration_minutes": 80,
    "notes": "gym was packed",
    "warmup": [{"number": 1, "name": "Arm circles", "reps": 20, "notes": "loose"}],
    "exercises": [
        {
            "number": 1,
            "name": "Squat",
            "notes": "trying to improve depth",
            "warmup_notes": "pyramid",
            "form_cues": ["brace"],
            "current_goal": {"weight_kg": 100.0, "sets": 3, "rep_range": {"min": 3, "max": 5},
                             "rest": {"minutes": 3}},
            "warmup_sets": [{"number": 1, "weight_kg": 60.0, "rep_count": 5, "notes": "easy"}],
            "sets": [
                {"number": 1, "weight_kg": 100.0, "rep_count": {"full": 3, "partial": 1},
                 "rpe": 8.5, "rep_quality_assessment": "good", "notes": "atg",
                 "rest": {"minutes": 3}, "heart_rate_bpm": 150},
                {"number": 2, "weight_kg": 100.0, "rep_count": {"full": 2, "partial": 0},
                 "rpe": 10, "failure_technique": {"technique_type": "LLP",
                                                  "details": {"partial_rep_count": 3}}},
            ],
        },
        {
            "number": 2,
            "name": "Single-arm row",
            "sets": [
                {"number": 1, "weight_kg": 30.0,
                 "unilateral_rep_count": {"left": {"full": 8, "partial": 0},
                                          "right": {"full": 7, "partial": 1}}},
            ],
        },
    ],
}


@pytest.fixture(scope="module")
def db_conn():
    conn = get_connection(TEST_DB_URL)
    apply_schema(conn)
    with conn.cursor() as cur:
        cur.execute("DELETE FROM sessions WHERE session_id = %s", (SOURCE_ID,))
    conn.commit()
    insert_session(conn, TrainingSession.model_validate(SOURCE), user_id=USER_A)
    yield conn
    with conn.cursor() as cur:
        # The source, plus every session confirmed from a repeat of it.
        cur.execute(
            "DELETE FROM sessions WHERE session_id = %s OR extraction_id IN ("
            "  SELECT x.id FROM extractions x JOIN raw_inputs r ON r.id = x.raw_input_id"
            "  WHERE r.source_kind = 'manual' AND r.source_file = %s)",
            (SOURCE_ID, SOURCE_ID),
        )
    conn.commit()
    conn.close()


@pytest.fixture(scope="module")
def client(db_conn):
    with TestClient(app_module()) as c:
        yield c


def app_module():
    from traininglogs.api.app import app

    return app


HEADERS = auth()


class TestSessionToExtract:
    @pytest.fixture
    def extract(self, db_conn):
        return session_to_extract(get_session(db_conn, SOURCE_ID), "2026-10-03")

    def test_session_plan_carries_over(self, extract) -> None:
        assert (extract.date, extract.focus, extract.program, extract.phase, extract.week) == (
            "2026-10-03", "Strength", "Test Program", 2, 3,
        )
        assert extract.uncertain_fields == ["date"]

    def test_how_that_day_went_is_cleared(self, extract) -> None:
        assert extract.notes is None and extract.session_duration_minutes is None
        squat = extract.exercises[0]
        assert squat.notes is None and squat.warmup_notes is None
        for s in squat.sets:
            assert (s.rpe, s.rep_quality_assessment, s.notes, s.failure_technique,
                    s.rest, s.heart_rate_bpm) == (None,) * 6
        assert squat.warmup_sets[0].notes is None
        assert extract.warmup[0].notes is None

    def test_weights_reps_and_goal_carry_over(self, extract) -> None:
        squat, row = extract.exercises
        assert [(s.number, s.weight_kg, s.rep_count.full, s.rep_count.partial) for s in squat.sets] == [
            (1, 100.0, 3, 1), (2, 100.0, 2, 0),
        ]
        assert (squat.warmup_sets[0].weight_kg, squat.warmup_sets[0].rep_count) == (60.0, 5)
        goal = squat.current_goal
        assert (goal.weight_kg, goal.sets, goal.rep_range.min, goal.rep_range.max,
                goal.rest.minutes) == (100.0, 3, 3, 5, 3)
        assert squat.form_cues == ["brace"]
        uni = row.sets[0].unilateral_rep_count
        assert (row.sets[0].rep_count, uni.left.full, uni.right.full, uni.right.partial) == (
            None, 8, 7, 1,
        )

    def test_movements_carry_over_without_notes(self, extract) -> None:
        assert [(m.name, m.reps) for m in extract.warmup] == [("Arm circles", 20)]


class TestRepeatSession:
    def test_writes_a_repeat_raw_input_and_pending_extraction(self, db_conn) -> None:
        now = datetime(2026, 10, 3, 14, 2, tzinfo=timezone.utc)
        raw_input_id, extraction_id = repeat_session(db_conn, SOURCE_ID, USER_A, now=now)

        raw = get_raw_input(db_conn, raw_input_id)
        assert (raw["source_kind"], raw["source_file"]) == ("manual", SOURCE_ID)
        assert raw["content"] == (
            f"Repeat of {SOURCE_ID} (Strength, 2026-09-19), started 2026-10-03T14:02:00+00:00 "
            f"[{raw_input_id}]"
        )
        extraction = get_extraction(db_conn, extraction_id)
        assert (extraction["status"], extraction["model"]) == ("pending", "none")
        assert extraction["extract"]["date"] == "2026-10-03"

        with db_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM llm_calls WHERE raw_input_id = %s", (raw_input_id,))
            assert cur.fetchone()[0] == 0

    def test_unknown_session_returns_none(self, db_conn) -> None:
        assert repeat_session(db_conn, "no-such-session", USER_A) is None


class TestRepeatApi:
    def test_repeat_then_confirm_twice_gives_two_sessions(self, client, db_conn) -> None:
        """Repeating the same session twice on the same day must not collide on session_id."""
        session_ids = []
        for _ in range(2):
            r = client.post(f"/sessions/{SOURCE_ID}/repeat", headers=HEADERS)
            assert r.status_code == 201
            extraction_id = r.json()["extraction_id"]

            card = client.get(f"/extractions/{extraction_id}", headers=HEADERS).json()
            assert [ex["header"]["name"] for ex in card["exercises"]] == ["Squat", "Single-arm row"]

            r = client.post(f"/extractions/{extraction_id}/confirm", headers=HEADERS)
            assert r.status_code == 201
            session_ids.append(r.json()["session_id"])

        assert session_ids[0] != session_ids[1]
        confirmed = get_session(db_conn, session_ids[0])
        assert [s["weight_kg"] for s in confirmed["exercises"][0]["sets"]] == [100, 100]

    def test_not_found(self, client) -> None:
        assert client.post("/sessions/no-such-session/repeat", headers=HEADERS).status_code == 404

    def test_requires_auth(self, client) -> None:
        assert client.post(f"/sessions/{SOURCE_ID}/repeat").status_code == 401

    def test_session_list_has_exercise_names_and_limit(self, client) -> None:
        r = client.get("/sessions", params={"from_date": "2026-09-19", "to_date": "2026-09-19"},
                       headers=HEADERS)
        source = next(s for s in r.json() if s["session_id"] == SOURCE_ID)
        assert source["exercises"] == ["Squat", "Single-arm row"]
        assert len(client.get("/sessions", params={"limit": 1}, headers=HEADERS).json()) == 1
