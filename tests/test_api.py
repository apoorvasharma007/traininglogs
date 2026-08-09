import os
import pytest


from fastapi.testclient import TestClient

from traininglogs.api.app import app
from traininglogs.db.db import get_connection, apply_schema
from traininglogs.db.insert import insert_session
from traininglogs.models.models import TrainingSession

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)

os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["API_KEY"] = "testkey"

SESSION_A = {
    "data_model_version": "0.0.1",
    "data_model_type": "TrainingSession",
    "session_id": "api-test-session-001",
    "user_id": "7",
    "user_name": "Apoorva Sharma",
    "date": "2026-02-01",
    "program": "Test Program",
    "program_author": "Test Author",
    "program_length_weeks": 12,
    "phase": 1,
    "week": 2,
    "is_deload_week": False,
    "focus": "Push Hypertrophy",
    "session_duration_minutes": 75,
    "exercises": [
        {
            "number": 1,
            "name": "Bench Press",
            "notes": None,
            "warmup_notes": None,
            "form_cues": ["brace core"],
            "target_muscle_groups": None,
            "rep_tempo": None,
            "current_goal": {
                "weight_kg": 80.0,
                "sets": 3,
                "rep_range": {"min": 5, "max": 6},
                "rest": {"minutes": 3},
            },
            "warmup_sets": [
                {"number": 1, "weight_kg": 60.0, "rep_count": 5, "notes": None}
            ],
            "sets": [
                {
                    "number": 1,
                    "weight_kg": 80.0,
                    "rep_count": {"full": 5, "partial": 0},
                    "rpe": 8.0,
                    "rep_quality_assessment": "good",
                    "notes": None,
                    "failure_technique": None,
                },
            ],
        }
    ],
}

SESSION_B = {
    **SESSION_A,
    "session_id": "api-test-session-002",
    "date": "2026-03-01",
    "phase": 2,
    "week": 1,
    "focus": "Pull Hypertrophy",
}


@pytest.fixture(scope="module")
def db_conn():
    conn = get_connection(TEST_DB_URL)
    apply_schema(conn)
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def client(db_conn):
    insert_session(db_conn, TrainingSession.model_validate(SESSION_A))
    insert_session(db_conn, TrainingSession.model_validate(SESSION_B))
    with TestClient(app) as c:
        yield c
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM sessions WHERE session_id LIKE 'api-test-%'")
    db_conn.commit()


def test_list_sessions_returns_all(client):
    r = client.get("/sessions", headers={"x-api-key": "testkey"})
    assert r.status_code == 200
    ids = [s["session_id"] for s in r.json()]
    assert "api-test-session-001" in ids
    assert "api-test-session-002" in ids


def test_list_sessions_filter_by_phase(client):
    r = client.get("/sessions?phase=1", headers={"x-api-key": "testkey"})
    assert r.status_code == 200
    results = r.json()
    assert all(s["phase"] == 1 for s in results)
    ids = [s["session_id"] for s in results]
    assert "api-test-session-001" in ids
    assert "api-test-session-002" not in ids


def test_list_sessions_filter_by_phase_and_week(client):
    r = client.get("/sessions?phase=2&week=1", headers={"x-api-key": "testkey"})
    assert r.status_code == 200
    results = [s for s in r.json() if s["session_id"].startswith("api-test-")]
    assert len(results) == 1
    assert results[0]["session_id"] == "api-test-session-002"


def test_list_sessions_filter_by_date_range(client):
    r = client.get(
        "/sessions?from_date=2026-02-01&to_date=2026-02-28",
        headers={"x-api-key": "testkey"},
    )
    assert r.status_code == 200
    test_results = [s for s in r.json() if s["session_id"].startswith("api-test-")]
    assert len(test_results) == 1
    assert test_results[0]["session_id"] == "api-test-session-001"


def test_session_detail_returns_full_structure(client):
    r = client.get("/sessions/api-test-session-001", headers={"x-api-key": "testkey"})
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == "api-test-session-001"
    assert body["focus"] == "Push Hypertrophy"
    assert len(body["exercises"]) == 1
    exercise = body["exercises"][0]
    assert exercise["name"] == "Bench Press"
    assert len(exercise["sets"]) == 1
    assert len(exercise["warmup_sets"]) == 1


def test_session_detail_not_found(client):
    r = client.get("/sessions/does-not-exist", headers={"x-api-key": "testkey"})
    assert r.status_code == 404


def test_exercise_history_returns_sets_in_order(client):
    r = client.get("/exercises/Bench Press/history", headers={"x-api-key": "testkey"})
    assert r.status_code == 200
    rows = [row for row in r.json() if row["session_id"].startswith("api-test-")]
    assert len(rows) == 2
    dates = [row["date"] for row in rows]
    assert dates == sorted(dates)


def test_exercise_history_case_insensitive(client):
    r = client.get("/exercises/bench press/history", headers={"x-api-key": "testkey"})
    assert r.status_code == 200
    rows = [row for row in r.json() if row["session_id"].startswith("api-test-")]
    assert len(rows) == 2


def test_exercise_history_not_found(client):
    r = client.get("/exercises/Squat/history", headers={"x-api-key": "testkey"})
    assert r.status_code == 404


def test_auth_rejects_wrong_key(client):
    r = client.get("/sessions", headers={"x-api-key": "wrongkey"})
    assert r.status_code == 401


def test_auth_rejects_missing_key(client):
    r = client.get("/sessions")
    assert r.status_code == 401


class TestCreateInput:
    """POST /inputs -- capture() then extract(), over HTTP. assemble() (the LLM boundary) is
    monkeypatched, same seam test_ingest.py and test_cli_log_ai_path.py use -- no real API
    calls."""

    def _fake_extract(self):
        from traininglogs.agent.schemas import TrainingLogLLMExtract
        from traininglogs.models.models import Exercise, RepCount, WorkingSet

        return TrainingLogLLMExtract(
            date="2026-03-01",
            focus="Legs Hypertrophy",
            exercises=[
                Exercise(
                    number=1,
                    name="Leg Press",
                    sets=[WorkingSet(number=1, weight_kg=280.0,
                                      rep_count=RepCount(full=12, partial=0), rpe=9.5)],
                )
            ],
        )

    def test_captures_and_extracts(self, client, db_conn, monkeypatch) -> None:
        monkeypatch.setattr(
            "traininglogs.ingest.extract.assemble",
            lambda text, provider=None: self._fake_extract(),
        )
        r = client.post(
            "/inputs",
            json={"content": "# Leg day\n1. 280 x 12 RPE 9.5", "source_kind": "markdown"},
            headers={"x-api-key": "testkey"},
        )
        assert r.status_code == 201
        body = r.json()
        assert body["raw_input_id"]
        assert body["extraction_id"]
        assert body["error"] is None

        with db_conn.cursor() as cur:
            cur.execute("SELECT content FROM raw_inputs WHERE id = %s", (body["raw_input_id"],))
            assert cur.fetchone()[0] == "# Leg day\n1. 280 x 12 RPE 9.5"
            cur.execute(
                "SELECT status FROM extractions WHERE id = %s", (body["extraction_id"],)
            )
            assert cur.fetchone()[0] == "pending"

    def test_extraction_failure_still_returns_the_raw_input_id(
        self, client, db_conn, monkeypatch
    ) -> None:
        """capture() commits before extract() is attempted -- a failed extraction must not
        lose the text, and the caller needs raw_input_id back to retry (extract() is
        idempotent) rather than resubmitting."""

        def failing_assemble(text, provider=None):
            raise RuntimeError("LLM unavailable")

        monkeypatch.setattr("traininglogs.ingest.extract.assemble", failing_assemble)

        r = client.post(
            "/inputs",
            json={"content": "some session text"},
            headers={"x-api-key": "testkey"},
        )
        assert r.status_code == 502
        body = r.json()
        assert body["raw_input_id"]
        assert body["extraction_id"] is None
        assert "LLM unavailable" in body["error"]

        with db_conn.cursor() as cur:
            cur.execute("SELECT content FROM raw_inputs WHERE id = %s", (body["raw_input_id"],))
            assert cur.fetchone()[0] == "some session text"

    def test_rejects_empty_content(self, client) -> None:
        r = client.post(
            "/inputs", json={"content": ""}, headers={"x-api-key": "testkey"}
        )
        assert r.status_code == 422

    def test_requires_auth(self, client) -> None:
        r = client.post("/inputs", json={"content": "some text"})
        assert r.status_code == 401


class TestGetExtractionCard:
    """GET /extractions/{id} -- the same card the CLI's confirm loop renders to a terminal,
    as JSON. ValidationCardBuilder is DB-free and already shared; this just adds a serializer
    in place of TerminalRenderer."""

    def _insert_extraction(self, db_conn) -> str:
        from traininglogs.db.insert import insert_extraction, insert_raw_input

        raw_input_id = insert_raw_input(db_conn, "# card test\n1. 280 x 12 RPE 9.5")
        extract = {
            "date": "2026-03-01",
            "focus": "Legs Hypertrophy",
            "exercises": [
                {
                    "number": 1,
                    "name": "Leg Press",
                    "sets": [
                        {"number": 1, "weight_kg": 280.0,
                         "rep_count": {"full": 12, "partial": 0}, "rpe": 9.5}
                    ],
                }
            ],
            "uncertain_fields": [],
        }
        return insert_extraction(
            db_conn, raw_input_id=raw_input_id, model="m", prompt_version="v1", extract=extract,
        )

    def test_returns_the_card(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn)
        r = client.get(f"/extractions/{extraction_id}", headers={"x-api-key": "testkey"})
        assert r.status_code == 200
        body = r.json()
        assert body["session_header"]["focus"] == "Legs Hypertrophy"
        assert len(body["exercises"]) == 1
        assert body["exercises"][0]["header"]["name"] == "Leg Press"
        assert body["exercises"][0]["working_set_rows"][0]["weight_kg"] == 280.0

    def test_not_found(self, client) -> None:
        r = client.get("/extractions/does-not-exist", headers={"x-api-key": "testkey"})
        assert r.status_code == 404

    def test_requires_auth(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn)
        r = client.get(f"/extractions/{extraction_id}")
        assert r.status_code == 401


class TestConfirmExtraction:
    """POST /extractions/{id}/confirm -- ingest.confirm() over HTTP. Content must be unique
    per test: session_id is derived from it now, so two tests using identical content would
    collide with each other, not just within a test. And because it's derived from content
    rather than a fresh tmp_path per run, the sessions this class creates must be cleaned up
    -- otherwise a second run of the suite against the same persistent test DB collides with
    the *previous* run's rows, not just within itself. Dates in this class are deliberately
    all "2026-05-0X" so teardown can find them by prefix."""

    @pytest.fixture(autouse=True)
    def _cleanup(self, db_conn):
        yield
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE session_id LIKE '2026-05-0%'")
        db_conn.commit()

    def _insert_extraction(self, db_conn, date: str, content: str, extraction_id=None) -> str:
        from traininglogs.db.insert import insert_extraction, insert_raw_input

        raw_input_id = insert_raw_input(db_conn, content)
        extract = {
            "date": date,
            "focus": "Legs Hypertrophy",
            "exercises": [
                {
                    "number": 1,
                    "name": "Leg Press",
                    "sets": [
                        {"number": 1, "weight_kg": 280.0,
                         "rep_count": {"full": 12, "partial": 0}, "rpe": 9.5}
                    ],
                }
            ],
            "uncertain_fields": [],
        }
        return insert_extraction(
            db_conn, raw_input_id=raw_input_id, model="m", prompt_version="v1", extract=extract,
            extraction_id=extraction_id,
        )

    def test_confirms_the_extraction_as_is(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn, "2026-05-01", "confirm test content 1")
        r = client.post(f"/extractions/{extraction_id}/confirm", headers={"x-api-key": "testkey"})
        assert r.status_code == 201
        session_id = r.json()["session_id"]
        assert session_id.startswith("2026-05-01-")

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT extraction_id FROM sessions WHERE session_id = %s", (session_id,)
            )
            assert cur.fetchone()[0] == extraction_id

    def test_confirms_with_an_extract_override(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn, "2026-05-02", "confirm test content 2")
        override = {
            "date": "2026-05-02",
            "focus": "Corrected Focus",
            "exercises": [
                {"number": 1, "name": "Leg Press", "sets": [
                    {"number": 1, "weight_kg": 280.0,
                     "rep_count": {"full": 12, "partial": 0}, "rpe": 9.5},
                ]},
            ],
        }
        corrections = [{
            "at": "2026-05-02T00:00:00Z", "instruction": "fix focus",
            "edits": [{"path": "focus", "value": "Corrected Focus"}],
        }]
        r = client.post(
            f"/extractions/{extraction_id}/confirm",
            json={"extract": override, "corrections": corrections},
            headers={"x-api-key": "testkey"},
        )
        assert r.status_code == 201
        session_id = r.json()["session_id"]

        with db_conn.cursor() as cur:
            cur.execute("SELECT focus FROM sessions WHERE session_id = %s", (session_id,))
            assert cur.fetchone()[0] == "Corrected Focus"

        from traininglogs.db.fetch import get_extraction
        assert get_extraction(db_conn, extraction_id)["corrections"] == corrections

    def test_duplicate_content_returns_409_not_a_crash(self, client, db_conn) -> None:
        id_a = self._insert_extraction(db_conn, "2026-05-03", "identical content for collision")
        r1 = client.post(f"/extractions/{id_a}/confirm", headers={"x-api-key": "testkey"})
        assert r1.status_code == 201

        id_b = self._insert_extraction(db_conn, "2026-05-03", "identical content for collision")
        r2 = client.post(f"/extractions/{id_b}/confirm", headers={"x-api-key": "testkey"})
        assert r2.status_code == 409

    def test_not_found(self, client) -> None:
        r = client.post("/extractions/does-not-exist/confirm", headers={"x-api-key": "testkey"})
        assert r.status_code == 404

    def test_requires_auth(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn, "2026-05-05", "auth test content")
        r = client.post(f"/extractions/{extraction_id}/confirm")
        assert r.status_code == 401
