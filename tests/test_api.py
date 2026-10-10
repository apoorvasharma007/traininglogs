import os
import re
import uuid

import pytest


from fastapi.testclient import TestClient

from traininglogs.api.app import app
from traininglogs.db.db import get_connection, apply_schema

from signed_in import USER_A, USER_B_AUTH, auth, clean_test_data, save_session

HEADERS = auth()

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://traininglogs:traininglogs@localhost:5433/traininglogs_test",
)

os.environ["DATABASE_URL"] = TEST_DB_URL

SESSION_A = {
    "data_model_version": "0.0.1",
    "data_model_type": "TrainingSession",
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


IDS: dict[str, str] = {}


@pytest.fixture(scope="module")
def client(db_conn):
    clean_test_data(db_conn)
    IDS["a"] = save_session(db_conn, SESSION_A)
    IDS["b"] = save_session(db_conn, SESSION_B)
    with TestClient(app) as c:
        yield c
    clean_test_data(db_conn)


def test_list_sessions_returns_all(client):
    r = client.get("/sessions", headers=HEADERS)
    assert r.status_code == 200
    assert [s["session_id"] for s in r.json()] == [IDS["b"], IDS["a"]], "newest first"


def test_list_sessions_filter_by_phase(client):
    r = client.get("/sessions?phase=1", headers=HEADERS)
    assert r.status_code == 200
    results = r.json()
    assert all(s["phase"] == 1 for s in results)
    ids = [s["session_id"] for s in results]
    assert IDS["a"] in ids
    assert IDS["b"] not in ids


def test_list_sessions_filter_by_phase_and_week(client):
    r = client.get("/sessions?phase=2&week=1", headers=HEADERS)
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["session_id"] == IDS["b"]


def test_list_sessions_filter_by_date_range(client):
    r = client.get(
        "/sessions?from_date=2026-02-01&to_date=2026-02-28",
        headers=HEADERS,
    )
    assert r.status_code == 200
    test_results = r.json()
    assert len(test_results) == 1
    assert test_results[0]["session_id"] == IDS["a"]


def test_session_list_has_exercise_names_and_a_limit(client):
    first = client.get("/sessions", headers=HEADERS).json()[0]
    assert first["exercises"] == ["Bench Press"]
    assert len(client.get("/sessions", params={"limit": 1}, headers=HEADERS).json()) == 1


def test_session_detail_returns_full_structure(client):
    r = client.get(f"/sessions/{IDS['a']}", headers=HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == IDS["a"]
    assert body["focus"] == "Push Hypertrophy"
    assert len(body["exercises"]) == 1
    exercise = body["exercises"][0]
    assert exercise["name"] == "Bench Press"
    assert len(exercise["sets"]) == 1
    assert len(exercise["warmup_sets"]) == 1


def test_session_detail_not_found(client):
    r = client.get("/sessions/does-not-exist", headers=HEADERS)
    assert r.status_code == 404


def test_exercise_history_returns_sets_in_order(client):
    r = client.get("/exercises/Bench Press/history", headers=HEADERS)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2
    dates = [row["date"] for row in rows]
    assert dates == sorted(dates)


def test_exercise_history_case_insensitive(client):
    r = client.get("/exercises/bench press/history", headers=HEADERS)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2


def test_exercise_history_not_found(client):
    r = client.get("/exercises/Squat/history", headers=HEADERS)
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

    def _fake_extract(self):  # noqa: D401
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
            json={"content": "# Leg day\n1. 280 x 12 RPE 9.5", "date": "2026-03-01", "source_kind": "text"},
            headers=HEADERS,
        )
        assert r.status_code == 201
        body = r.json()
        assert body["raw_input_id"]
        assert body["extraction_id"]
        assert body["error"] is None

        with db_conn.cursor() as cur:
            cur.execute("SELECT content FROM input_text WHERE id = %s", (body["raw_input_id"],))
            assert cur.fetchone()[0] == "# Leg day\n1. 280 x 12 RPE 9.5"
            cur.execute(
                "SELECT status FROM input_text_confirmation_cards WHERE id = %s", (body["extraction_id"],)
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
            json={"content": "some session text", "date": "2026-03-01"},
            headers=HEADERS,
        )
        assert r.status_code == 502
        body = r.json()
        assert body["raw_input_id"]
        assert body["extraction_id"] is None
        assert body["error"].startswith("Couldn't read your note.")

        with db_conn.cursor() as cur:
            cur.execute("SELECT content FROM input_text WHERE id = %s", (body["raw_input_id"],))
            assert cur.fetchone()[0] == "some session text"

    def test_rejects_empty_content(self, client) -> None:
        r = client.post(
            "/inputs", json={"content": "", "date": "2026-03-01"}, headers=HEADERS
        )
        assert r.status_code == 422

    def test_requires_the_phones_date(self, client) -> None:
        r = client.post("/inputs", json={"content": "some text"}, headers=HEADERS)
        assert r.status_code == 422

    def test_requires_auth(self, client) -> None:
        r = client.post("/inputs", json={"content": "some text"})
        assert r.status_code == 401


class TestGetExtractionCard:
    """GET /extractions/{id} -- the same card the CLI's confirm loop renders to a terminal,
    as JSON. ValidationCardBuilder is DB-free and already shared; this just adds a serializer
    in place of TerminalRenderer."""

    def _insert_extraction(self, db_conn) -> str:
        from traininglogs.db.insert import insert_card, insert_input

        raw_input_id = insert_input(db_conn, USER_A, "# card test\n1. 280 x 12 RPE 9.5")
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
        return insert_card(db_conn, USER_A, raw_input_id, "m", "v1", extract)

    def test_returns_the_card(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn)
        r = client.get(f"/extractions/{extraction_id}", headers=HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["session_header"]["focus"] == "Legs Hypertrophy"
        assert len(body["exercises"]) == 1
        assert body["exercises"][0]["header"]["name"] == "Leg Press"
        assert body["exercises"][0]["working_set_rows"][0]["weight_kg"] == 280.0

    def test_not_found(self, client) -> None:
        r = client.get("/extractions/does-not-exist", headers=HEADERS)
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
            cur.execute("DELETE FROM workout_sessions WHERE date::text LIKE '2026-05-0%'")
        db_conn.commit()

    def _insert_extraction(self, db_conn, date: str, content: str, extraction_id=None) -> str:
        from traininglogs.db.insert import insert_card, insert_input

        raw_input_id = insert_input(db_conn, USER_A, content)
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
        return insert_card(db_conn, USER_A, raw_input_id, "m", "v1", extract)

    def test_confirms_the_extraction_as_is(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn, "2026-05-01", "confirm test content 1")
        r = client.post(f"/extractions/{extraction_id}/confirm", headers=HEADERS)
        assert r.status_code == 201
        session_id = r.json()["session_id"]
        uuid.UUID(session_id)

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT confirmation_card_id::text FROM workout_sessions WHERE id = %s", (session_id,)
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
            headers=HEADERS,
        )
        assert r.status_code == 201
        session_id = r.json()["session_id"]

        with db_conn.cursor() as cur:
            cur.execute("SELECT focus FROM workout_sessions WHERE id = %s", (session_id,))
            assert cur.fetchone()[0] == "Corrected Focus"

        from traininglogs.db.fetch import get_card
        assert get_card(db_conn, USER_A, extraction_id)["corrections"] == corrections

    def test_confirm_counts_as_a_planned_workout(self, client, db_conn) -> None:
        from traininglogs.db.programs import add_workout, create_program

        program_id = create_program(db_conn, USER_A, "Confirm test program")
        workout_id = add_workout(db_conn, USER_A, program_id, "Bench")
        extraction_id = self._insert_extraction(db_conn, "2026-05-08", "confirm test content 8")
        try:
            r = client.post(
                f"/extractions/{extraction_id}/confirm",
                json={"program_workout_id": workout_id},
                headers=HEADERS,
            )
            assert r.status_code == 201
            with db_conn.cursor() as cur:
                cur.execute(
                    "SELECT program_workout_id::text FROM workout_sessions WHERE id = %s",
                    (r.json()["session_id"],),
                )
                assert cur.fetchone()[0] == workout_id
        finally:
            with db_conn.cursor() as cur:
                cur.execute("DELETE FROM workout_sessions WHERE program_workout_id = %s", (workout_id,))
                cur.execute("DELETE FROM program_workouts WHERE program_id = %s", (program_id,))
                cur.execute("DELETE FROM programs WHERE id = %s", (program_id,))
            db_conn.commit()

    def test_confirm_with_an_unknown_workout_saves_nothing(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn, "2026-05-09", "confirm test content 9")
        r = client.post(
            f"/extractions/{extraction_id}/confirm",
            json={"program_workout_id": "nope"},
            headers=HEADERS,
        )
        assert r.status_code == 422
        with db_conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM workout_sessions WHERE date = '2026-05-09'")
            assert cur.fetchone()[0] == 0

    def test_duplicate_content_returns_409_not_a_crash(self, client, db_conn) -> None:
        id_a = self._insert_extraction(db_conn, "2026-05-03", "identical content for collision")
        r1 = client.post(f"/extractions/{id_a}/confirm", headers=HEADERS)
        assert r1.status_code == 201

        id_b = self._insert_extraction(db_conn, "2026-05-03", "identical content for collision")
        r2 = client.post(f"/extractions/{id_b}/confirm", headers=HEADERS)
        assert r2.status_code == 409
        assert r2.json() == {"detail": "This note is already saved.", "session_id": r1.json()["session_id"]}

    def test_a_card_confirms_once_even_with_a_changed_date(self, client, db_conn) -> None:
        """Swiping back to a saved card, changing the date and confirming again must not save a
        second copy; the answer links to the first."""
        extraction_id = self._insert_extraction(db_conn, "2026-05-10", "confirm once content")
        r1 = client.post(f"/extractions/{extraction_id}/confirm", headers=HEADERS)
        assert r1.status_code == 201
        with db_conn.cursor() as cur:
            cur.execute("SELECT extract FROM input_text_confirmation_cards WHERE id = %s", (extraction_id,))
            changed = {**cur.fetchone()[0], "date": "2026-05-09"}
        r2 = client.post(f"/extractions/{extraction_id}/confirm", json={"extract": changed}, headers=HEADERS)
        assert r2.status_code == 409
        assert r2.json()["session_id"] == r1.json()["session_id"]
        with db_conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM workout_sessions WHERE confirmation_card_id = %s", (extraction_id,))
            assert cur.fetchone()[0] == 1

    def test_not_found(self, client) -> None:
        r = client.post("/extractions/does-not-exist/confirm", headers=HEADERS)
        assert r.status_code == 404

    def test_requires_auth(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn, "2026-05-05", "auth test content")
        r = client.post(f"/extractions/{extraction_id}/confirm")
        assert r.status_code == 401


class TestCorrectExtraction:
    """POST /extractions/{id}/correct -- fully stateless. LLMExtractValidator.apply_correction
    (the actual LLM boundary) is monkeypatched at the class method level, since AnthropicProvider
    is constructed inside the endpoint itself, not injectable -- no real API calls."""

    def _insert_extraction(self, db_conn, date: str, content: str) -> str:
        from traininglogs.db.insert import insert_card, insert_input

        raw_input_id = insert_input(db_conn, USER_A, content)
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
        return insert_card(db_conn, USER_A, raw_input_id, "m", "v1", extract)

    def _stub_correction(self, monkeypatch, new_focus: str) -> None:
        from traininglogs.agent.patch import FieldEdit

        def fake_apply_correction(self_, extract, instruction):
            updated = extract.model_copy(update={"focus": new_focus})
            return updated, [FieldEdit(path="focus", value=new_focus)]

        monkeypatch.setattr(
            "traininglogs.agent.llm_extract_validator.LLMExtractValidator.apply_correction",
            fake_apply_correction,
        )

    def test_corrects_the_extraction_own_reading_when_no_extract_given(
        self, client, db_conn, monkeypatch
    ) -> None:
        extraction_id = self._insert_extraction(db_conn, "2026-06-01", "correct test content 1")
        self._stub_correction(monkeypatch, "Corrected Focus")

        r = client.post(
            f"/extractions/{extraction_id}/correct",
            json={"instruction": "it was actually a different focus"},
            headers=HEADERS,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["extract"]["focus"] == "Corrected Focus"
        assert body["card"]["session_header"]["focus"] == "Corrected Focus"
        assert body["correction"]["instruction"] == "it was actually a different focus"
        assert body["correction"]["source"] == "ai"
        assert body["correction"]["edits"] == [{"path": "focus", "value": "Corrected Focus"}]

    def test_a_second_correction_builds_on_the_extract_the_client_sends_back(
        self, client, db_conn, monkeypatch
    ) -> None:
        """Statelessness, proven: the server never remembers the first correction -- it only
        knows about it because the client sent `extract` back."""
        extraction_id = self._insert_extraction(db_conn, "2026-06-02", "correct test content 2")

        self._stub_correction(monkeypatch, "First Correction")
        r1 = client.post(
            f"/extractions/{extraction_id}/correct",
            json={"instruction": "fix 1"},
            headers=HEADERS,
        )
        first_extract = r1.json()["extract"]

        self._stub_correction(monkeypatch, "Second Correction")
        r2 = client.post(
            f"/extractions/{extraction_id}/correct",
            json={"extract": first_extract, "instruction": "fix 2"},
            headers=HEADERS,
        )
        assert r2.json()["extract"]["focus"] == "Second Correction"

        # The extraction's own stored reading was never touched by either call.
        from traininglogs.db.fetch import get_card
        assert get_card(db_conn, USER_A, extraction_id)["extract"]["focus"] == "Legs Hypertrophy"

    def test_an_unresolvable_path_returns_400_not_a_crash(self, client, db_conn, monkeypatch) -> None:
        def fake_apply_correction(self_, extract, instruction):
            from traininglogs.agent.patch import PatchError
            raise PatchError("'nonexistent_field' is not a field here")

        monkeypatch.setattr(
            "traininglogs.agent.llm_extract_validator.LLMExtractValidator.apply_correction",
            fake_apply_correction,
        )
        extraction_id = self._insert_extraction(db_conn, "2026-06-03", "correct test content 3")

        r = client.post(
            f"/extractions/{extraction_id}/correct",
            json={"instruction": "change the nonexistent field"},
            headers=HEADERS,
        )
        assert r.status_code == 400

    def _llm_calls_for(self, db_conn, extraction_id: str) -> list[tuple]:
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT l.step, l.cost_usd, l.failed FROM ai_call_logs l "
                "JOIN input_text_confirmation_cards c ON c.input_id = l.input_id WHERE c.id = %s",
                (extraction_id,),
            )
            return cur.fetchall()

    def _stub_spending_correction(self, monkeypatch, fail: bool) -> None:
        """A correction that records one call on its provider, as the real one does, then
        either succeeds or fails the way a bad model reply would."""
        from traininglogs.agent.patch import FieldEdit
        from traininglogs.agent.schemas import LLMParserError

        def fake_apply_correction(self_, extract, instruction):
            self_._provider.calls.append({
                "step": "edit_extraction", "model": "m", "attempts": 1, "input_tokens": 100,
                "output_tokens": 10, "cost_usd": 0.0012, "ms": 5, "cached": False,
                "failed": "bad reply" if fail else None, "raw_payload": None,
            })
            if fail:
                raise LLMParserError("bad reply")
            return extract.model_copy(update={"focus": "X"}), [FieldEdit(path="focus", value="X")]

        monkeypatch.setattr(
            "traininglogs.agent.llm_extract_validator.LLMExtractValidator.apply_correction",
            fake_apply_correction,
        )

    def test_correction_cost_is_logged(self, client, db_conn, monkeypatch) -> None:
        extraction_id = self._insert_extraction(db_conn, "2026-06-06", "correct test content 6")
        self._stub_spending_correction(monkeypatch, fail=False)
        r = client.post(
            f"/extractions/{extraction_id}/correct",
            json={"instruction": "fix it"},
            headers=HEADERS,
        )
        assert r.status_code == 200
        calls = self._llm_calls_for(db_conn, extraction_id)
        assert [(step, float(cost), failed) for step, cost, failed in calls] == [
            ("edit_extraction", 0.0012, None)
        ]

    def test_failed_correction_cost_is_still_logged(self, client, db_conn, monkeypatch) -> None:
        extraction_id = self._insert_extraction(db_conn, "2026-06-07", "correct test content 7")
        self._stub_spending_correction(monkeypatch, fail=True)
        r = client.post(
            f"/extractions/{extraction_id}/correct",
            json={"instruction": "fix it"},
            headers=HEADERS,
        )
        assert r.status_code == 502
        assert [c[2] for c in self._llm_calls_for(db_conn, extraction_id)] == ["bad reply"]

    def test_not_found(self, client) -> None:
        r = client.post(
            "/extractions/does-not-exist/correct",
            json={"instruction": "fix it"},
            headers=HEADERS,
        )
        assert r.status_code == 404

    def test_rejects_empty_instruction(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn, "2026-06-04", "correct test content 4")
        r = client.post(
            f"/extractions/{extraction_id}/correct",
            json={"instruction": ""},
            headers=HEADERS,
        )
        assert r.status_code == 422

    def test_requires_auth(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn, "2026-06-05", "correct test content 5")
        r = client.post(
            f"/extractions/{extraction_id}/correct", json={"instruction": "fix it"}
        )
        assert r.status_code == 401


class TestEditExtraction:
    """POST /extractions/{id}/edit -- values changed on the card, applied with no LLM call.
    Same statelessness and reply shape as /correct."""

    def _insert_extraction(self, db_conn, content: str) -> str:
        from traininglogs.db.insert import insert_card, insert_input

        raw_input_id = insert_input(db_conn, USER_A, content)
        extract = {
            "date": "2026-07-01",
            "focus": "Push",
            "exercises": [
                {
                    "number": 1,
                    "name": "Bench",
                    "sets": [
                        {"number": 1, "weight_kg": 60.0,
                         "rep_count": {"full": 12, "partial": 0}, "rpe": 8.0}
                    ],
                }
            ],
            "uncertain_fields": ["exercises.0.sets.0.rpe"],
        }
        return insert_card(db_conn, USER_A, raw_input_id, "m", "v1", extract)

    def _post(self, client, extraction_id: str, body: dict, auth: bool = True):
        headers = HEADERS if auth else {}
        return client.post(f"/extractions/{extraction_id}/edit", json=body, headers=headers)

    def test_applies_edit_and_returns_extract_card_and_correction(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn, "edit test content 1")
        r = self._post(client, extraction_id, {"edits": [
            {"path": "exercises.0.sets.0", "field": "rpe", "value": 9},
            {"path": "exercises.0.sets.0", "field": "reps", "value": "15"},
        ]})
        assert r.status_code == 200
        body = r.json()
        assert body["extract"]["exercises"][0]["sets"][0]["rpe"] == 9
        assert body["extract"]["uncertain_fields"] == []
        row = body["card"]["exercises"][0]["working_set_rows"][0]
        assert (row["rpe"], row["reps"], row["path"]) == (9, "15", "exercises.0.sets.0")
        assert body["correction"]["source"] == "manual"
        assert "instruction" not in body["correction"]
        assert {"path": "exercises.0.sets.0.rpe", "value": 9} in body["correction"]["edits"]

    def test_builds_on_the_extract_the_client_sends_back(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn, "edit test content 2")
        first = self._post(client, extraction_id, {"edits": [
            {"path": "", "field": "focus", "value": "Upper"},
        ]}).json()["extract"]
        r = self._post(client, extraction_id, {"extract": first, "edits": [
            {"path": "exercises.0", "field": "name", "value": "Incline Bench"},
        ]})
        body = r.json()
        assert (body["extract"]["focus"], body["extract"]["exercises"][0]["name"]) == (
            "Upper", "Incline Bench",
        )

        from traininglogs.db.fetch import get_card
        assert get_card(db_conn, USER_A, extraction_id)["extract"]["focus"] == "Push"

    def test_invalid_value_returns_400_naming_the_field(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn, "edit test content 3")
        r = self._post(client, extraction_id, {"edits": [
            {"path": "exercises.0.sets.0", "field": "rpe", "value": 85},
        ]})
        assert r.status_code == 400
        assert "exercises.0.sets.0.rpe" in r.json()["detail"]

    def test_non_editable_field_returns_400(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn, "edit test content 4")
        r = self._post(client, extraction_id, {"edits": [
            {"path": "exercises.0.sets.0", "field": "failure_technique", "value": "x"},
        ]})
        assert r.status_code == 400

    def test_rejects_empty_edit_list(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn, "edit test content 5")
        assert self._post(client, extraction_id, {"edits": []}).status_code == 422

    def test_not_found(self, client) -> None:
        r = self._post(client, "does-not-exist", {"edits": [
            {"path": "", "field": "focus", "value": "x"},
        ]})
        assert r.status_code == 404

    def test_requires_auth(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn, "edit test content 6")
        r = self._post(client, extraction_id, {"edits": [
            {"path": "", "field": "focus", "value": "x"},
        ]}, auth=False)
        assert r.status_code == 401

    def test_add_set_op_returns_created_path_and_records_the_op(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn, "edit test content 7")
        r = self._post(client, extraction_id, {"op": {"op": "add_set", "path": "exercises.0"}})
        assert r.status_code == 200
        body = r.json()
        assert body["created_path"] == "exercises.0.sets.1"
        rows = body["card"]["exercises"][0]["working_set_rows"]
        assert [(row["number"], row["path"]) for row in rows] == [
            (1, "exercises.0.sets.0"), (2, "exercises.0.sets.1"),
        ]
        assert (body["correction"]["op"], body["correction"]["path"]) == ("add_set", "exercises.0")
        assert body["correction"]["edits"][0]["path"] == "exercises.0.sets"

    def test_remove_op(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn, "edit test content 8")
        r = self._post(client, extraction_id, {"op": {"op": "remove", "path": "exercises.0.sets.0"}})
        assert r.status_code == 200
        assert r.json()["card"]["exercises"][0]["working_set_rows"] == []
        assert r.json()["created_path"] is None

    def test_op_on_wrong_line_returns_400(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn, "edit test content 9")
        r = self._post(client, extraction_id, {"op": {"op": "remove", "path": ""}})
        assert r.status_code == 400

    def test_edits_and_op_together_rejected(self, client, db_conn) -> None:
        extraction_id = self._insert_extraction(db_conn, "edit test content 10")
        r = self._post(client, extraction_id, {
            "edits": [{"path": "", "field": "focus", "value": "x"}],
            "op": {"op": "add_set", "path": "exercises.0"},
        })
        assert r.status_code == 422


class TestWebUi:
    """The app (frontend/dist, built by `npm run build`) is served by the API itself (same origin,
    one deploy), and mounted after every API route so it can't shadow one. index.html is never
    cached; the hashed files under assets/ are kept until a release renames them."""

    def test_index_served_without_auth_and_not_cached(self, client) -> None:
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert 'id="root"' in r.text
        assert r.headers["cache-control"] == "no-cache"

    def test_hashed_assets_cached_until_renamed(self, client) -> None:
        script = re.search(r'src="(/assets/[^"]+\.js)"', client.get("/").text).group(1)
        r = client.get(script)
        assert r.status_code == 200
        assert r.headers["cache-control"] == "public, max-age=31536000, immutable"

    def test_missing_asset_not_cached(self, client) -> None:
        r = client.get("/assets/not-a-file.js")
        assert r.status_code == 404
        assert "immutable" not in r.headers.get("cache-control", "")

    def test_app_compressed_when_browser_accepts_it(self, client) -> None:
        script = re.search(r'src="(/assets/[^"]+\.js)"', client.get("/").text).group(1)
        assert client.get(script, headers={"Accept-Encoding": "gzip"}).headers["content-encoding"] == "gzip"
        assert "content-encoding" not in client.get(script, headers={"Accept-Encoding": "identity"}).headers

    def test_old_app_address_redirects(self, client) -> None:
        r = client.get("/app/", follow_redirects=False)
        assert (r.status_code, r.headers["location"]) == (301, "/")

    def test_api_routes_still_take_precedence(self, client) -> None:
        assert client.get("/sessions").status_code == 401
        assert client.get("/sessions", headers=HEADERS).status_code == 200


class TestDeadConnections:
    """Supabase closes idle connections. The pool must replace them instead of failing every
    request until a restart."""

    def test_requests_work_after_the_server_closes_the_pool_connections(self, client, monkeypatch) -> None:
        import traininglogs.api.app as api_app

        # Treat every pooled connection as idle, as after a quiet spell.
        monkeypatch.setattr(api_app, "IDLE_CHECK_SECONDS", -1.0)
        headers = HEADERS
        assert client.get("/sessions?limit=1", headers=headers).status_code == 200
        killer = get_connection(TEST_DB_URL)
        with killer.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE application_name = 'traininglogs-api' AND pid <> pg_backend_pid()"
            )
            assert cur.rowcount >= 1
        killer.close()
        for _ in range(3):
            assert client.get("/sessions?limit=1", headers=headers).status_code == 200
