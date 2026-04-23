import os
from contextlib import asynccontextmanager
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query

from traininglogs.db.db import apply_schema, get_connection
from traininglogs.db.fetch import get_exercise_history, get_session, get_sessions

load_dotenv()

API_KEY = os.environ.get("API_KEY", "")


def _db():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def _auth(x_api_key: Annotated[str, Header()] = ""):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = get_connection()
    apply_schema(conn)
    conn.close()
    yield


app = FastAPI(title="traininglogs", lifespan=lifespan)


@app.get("/sessions")
def list_sessions(
    phase: int | None = Query(None),
    week: int | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    conn=Depends(_db),
    _=Depends(_auth),
):
    return get_sessions(conn, phase=phase, week=week, from_date=from_date, to_date=to_date)


@app.get("/sessions/{session_id}")
def session_detail(session_id: str, conn=Depends(_db), _=Depends(_auth)):
    session = get_session(conn, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.get("/exercises/{name}/history")
def exercise_history(name: str, conn=Depends(_db), _=Depends(_auth)):
    rows = get_exercise_history(conn, name)
    if not rows:
        raise HTTPException(status_code=404, detail="No history found for this exercise")
    return rows
