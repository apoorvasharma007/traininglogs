import os
import sys
from contextlib import asynccontextmanager
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.pool import SimpleConnectionPool

from traininglogs.db.fetch import get_exercise_history, get_session, get_sessions
from traininglogs.api.schemas import (
    CaptureIn,
    CaptureOut,
    ExerciseHistoryRow,
    SessionDetail,
    SessionSummary,
)

load_dotenv()

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "").split(",")

_pool: SimpleConnectionPool | None = None


def _get_pool() -> SimpleConnectionPool:
    global _pool
    if _pool is None:
        db_url = os.environ["DATABASE_URL"]
        _pool = SimpleConnectionPool(minconn=1, maxconn=10, dsn=db_url)
    return _pool


def _db():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


def _auth(x_api_key: Annotated[str, Header()] = ""):
    api_key = os.environ.get("API_KEY", "")
    if api_key and x_api_key != api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not os.environ.get("API_KEY"):
        print(
            "ERROR: API_KEY is not set. Set it in .env before starting the server.",
            file=sys.stderr,
        )
        sys.exit(1)
    _get_pool()
    yield
    if _pool:
        _pool.closeall()


app = FastAPI(title="traininglogs", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if ALLOWED_ORIGINS != [""] else [],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-Api-Key", "Content-Type"],
)


@app.get("/sessions", response_model=list[SessionSummary])
def list_sessions(
    phase: int | None = Query(None),
    week: int | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    conn=Depends(_db),
    _=Depends(_auth),
):
    return get_sessions(conn, phase=phase, week=week, from_date=from_date, to_date=to_date)


@app.get("/sessions/{session_id}", response_model=SessionDetail)
def session_detail(session_id: str, conn=Depends(_db), _=Depends(_auth)):
    session = get_session(conn, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.get("/exercises/{name}/history", response_model=list[ExerciseHistoryRow])
def exercise_history(name: str, conn=Depends(_db), _=Depends(_auth)):
    rows = get_exercise_history(conn, name)
    if not rows:
        raise HTTPException(status_code=404, detail="No history found for this exercise")
    return rows


@app.post("/inputs", response_model=CaptureOut)
def create_input(body: CaptureIn, response: Response, conn=Depends(_db), _=Depends(_auth)):
    """capture() then extract() -- the same two ingest/ functions cli/log.py calls, over HTTP.

    capture() commits before extract() is ever attempted, so a failed extraction still leaves
    `raw_input_id` in the response -- the text is not lost, and the caller can retry extraction
    against the same raw input (extract() is idempotent) rather than resubmitting it.
    """
    from traininglogs.agent.providers import AnthropicProvider
    from traininglogs.ingest.capture import capture
    from traininglogs.ingest.extract import extract

    raw_input_id = capture(
        conn, body.content, source_kind=body.source_kind, source_file=body.source_file
    )

    try:
        provider = AnthropicProvider()
        extraction_id = extract(conn, raw_input_id, provider=provider, model=provider.model)
    except Exception as exc:
        response.status_code = 502
        return CaptureOut(raw_input_id=raw_input_id, error=str(exc))

    response.status_code = 201
    return CaptureOut(raw_input_id=raw_input_id, extraction_id=extraction_id)


@app.get("/extractions/{extraction_id}")
def get_extraction_card(extraction_id: str, conn=Depends(_db), _=Depends(_auth)):
    """The same card the CLI's confirm loop renders to a terminal, as JSON instead --
    ValidationCardBuilder is DB-free and shared by both, only the renderer differs.
    """
    from fastapi.encoders import jsonable_encoder

    from traininglogs.agent.schemas import TrainingLogLLMExtract
    from traininglogs.agent.validation_card_builder import ValidationCardBuilder
    from traininglogs.db.fetch import get_extraction

    stored = get_extraction(conn, extraction_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Extraction not found")

    extract_obj = TrainingLogLLMExtract.model_validate(stored["extract"])
    card = ValidationCardBuilder().build(extract_obj)
    return jsonable_encoder(card)
