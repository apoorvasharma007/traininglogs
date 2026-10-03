import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from psycopg2.pool import SimpleConnectionPool

from traininglogs.db.fetch import get_exercise_history, get_session, get_sessions
from traininglogs.api.schemas import (
    CaptureIn,
    CaptureOut,
    ConfirmIn,
    ConfirmOut,
    CorrectIn,
    CorrectOut,
    EditIn,
    ExerciseHistoryRow,
    LiftDetail,
    LiftsOut,
    PinIn,
    PinOut,
    ProgramIn,
    ProgramOut,
    ProgramPatch,
    SessionDetail,
    SessionSummary,
    WorkoutExercisesIn,
    WorkoutIn,
    WorkoutOrderIn,
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
        # A connection pool reuses the same physical connection across unrelated requests.
        # Without this, a request that opens a transaction and never explicitly commits or
        # rolls back (every GET endpoint; the early "already exists" return in
        # insert_session()) hands the connection back to the pool mid-transaction. The next
        # request to get that connection then runs inside that leftover transaction and sees
        # its uncommitted writes as if they were its own -- invisible to every other
        # connection, including a test's own, but very visible to itself. Rollback is a safe
        # no-op when everything was already committed.
        conn.rollback()
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
    global _pool
    _get_pool()
    yield
    if _pool:
        _pool.closeall()
        # Forget it, so a later startup in the same process (a second TestClient) builds a new
        # pool instead of handing out connections from this closed one.
        _pool = None


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
    limit: int | None = Query(None, ge=1, le=500),
    conn=Depends(_db),
    _=Depends(_auth),
):
    return get_sessions(
        conn, phase=phase, week=week, from_date=from_date, to_date=to_date, limit=limit
    )


@app.post("/sessions/{session_id}/repeat", response_model=CaptureOut, status_code=201)
def repeat_session_endpoint(session_id: str, conn=Depends(_db), _=Depends(_auth)):
    """Start a new session from a past one -- no LLM call. Returns the same ids as
    POST /inputs, so the client loads and confirms the card exactly as after an extraction.
    """
    from traininglogs.ingest.repeat import repeat_session

    ids = repeat_session(conn, session_id)
    if ids is None:
        raise HTTPException(status_code=404, detail="Session not found")
    raw_input_id, extraction_id = ids
    return CaptureOut(raw_input_id=raw_input_id, extraction_id=extraction_id)


@app.get("/sessions/{session_id}", response_model=SessionDetail)
def session_detail(session_id: str, conn=Depends(_db), _=Depends(_auth)):
    session = get_session(conn, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.get("/progress/lifts", response_model=LiftsOut)
def progress_lifts(conn=Depends(_db), _=Depends(_auth)):
    """Key lifts, then other lifts trained in 3 or more sessions: each with its latest and best
    estimated max (or best reps at bodyweight), and the trend over the last 4 weeks."""
    from datetime import date

    from traininglogs.analytics.progress import lift_summaries
    from traininglogs.db.fetch import get_working_set_rows

    return lift_summaries(get_working_set_rows(conn), date.today())


@app.get("/progress/lifts/{name}", response_model=LiftDetail)
def progress_lift(name: str, conn=Depends(_db), _=Depends(_auth)):
    """One lift's sessions, oldest first: the value, the set behind it, records and goal."""
    from datetime import date

    from traininglogs.analytics.progress import lift_detail
    from traininglogs.db.fetch import get_working_set_rows

    detail = lift_detail(get_working_set_rows(conn), name, date.today())
    if detail is None:
        raise HTTPException(status_code=404, detail="No lift with that name")
    return detail


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


@app.post("/extractions/{extraction_id}/confirm", response_model=ConfirmOut)
def confirm_extraction_endpoint(
    extraction_id: str,
    response: Response,
    body: ConfirmIn = ConfirmIn(),
    conn=Depends(_db),
    _=Depends(_auth),
):
    """ingest.confirm() over HTTP. `body.extract` lets a client submit the result of one or
    more /correct calls; omitted, the extraction's own stored reading is confirmed as-is.
    """
    from traininglogs.agent.schemas import TrainingLogLLMExtract
    from traininglogs.db.fetch import get_extraction
    from traininglogs.ingest.confirm import confirm

    stored = get_extraction(conn, extraction_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Extraction not found")

    extract_dict = body.extract if body.extract is not None else stored["extract"]
    final_extract = TrainingLogLLMExtract.model_validate(extract_dict)

    if body.program_workout_id is not None:
        from traininglogs.db.programs import workout_program_id

        if workout_program_id(conn, body.program_workout_id) is None:
            raise HTTPException(status_code=422, detail="That workout doesn't exist or was removed.")

    try:
        session = confirm(conn, extraction_id, final_extract, corrections=body.corrections)
    except SystemExit as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    if body.program_workout_id is not None:
        from traininglogs.db.programs import link_session_to_workout

        link_session_to_workout(conn, session.session_id, body.program_workout_id)

    response.status_code = 201
    return ConfirmOut(session_id=session.session_id)


@app.post("/extractions/{extraction_id}/correct", response_model=CorrectOut)
def correct_extraction(
    extraction_id: str, body: CorrectIn, conn=Depends(_db), _=Depends(_auth)
):
    """Apply one correction and hand back the result -- fully stateless, same as every other
    endpoint here. `body.extract` (the previous response's own `extract`) carries state
    between calls instead of the server holding any; the extraction's own stored reading is
    the starting point when it's omitted, on the first correction.
    """
    from datetime import datetime, timezone

    from fastapi.encoders import jsonable_encoder

    from traininglogs.agent.llm_extract_validator import LLMExtractValidator
    from traininglogs.agent.patch import PatchError
    from traininglogs.agent.providers import AnthropicProvider
    from traininglogs.agent.schemas import LLMParserError, TrainingLogLLMExtract
    from traininglogs.agent.validation_card_builder import ValidationCardBuilder
    from traininglogs.db.fetch import get_extraction
    from traininglogs.db.insert import insert_llm_calls

    stored = get_extraction(conn, extraction_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Extraction not found")

    extract_dict = body.extract if body.extract is not None else stored["extract"]
    current_extract = TrainingLogLLMExtract.model_validate(extract_dict)

    provider = AnthropicProvider()
    validator = LLMExtractValidator(provider)
    try:
        updated_extract, edits = validator.apply_correction(current_extract, body.instruction)
    except PatchError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LLMParserError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        # Logged whether the correction worked or not, same as extraction does: a failed
        # correction still cost money. Tied to the raw input, so a session's total cost is one
        # query across extraction and corrections alike.
        insert_llm_calls(conn, stored["raw_input_id"], provider.calls)

    correction = {
        "at": datetime.now(timezone.utc).isoformat(),
        "source": "ai",
        "instruction": body.instruction,
        "edits": [e.model_dump(mode="json") for e in edits],
    }
    card = ValidationCardBuilder().build(updated_extract)

    return CorrectOut(
        extract=updated_extract.model_dump(mode="json"),
        card=jsonable_encoder(card),
        correction=correction,
    )


@app.post("/extractions/{extraction_id}/edit", response_model=CorrectOut)
def edit_extraction(extraction_id: str, body: EditIn, conn=Depends(_db), _=Depends(_auth)):
    """Apply values changed directly on the card, or add/remove one line -- no LLM call.
    Stateless and round-tripped exactly like /correct, and replies in the same shape, so a
    client treats both alike.
    """
    from datetime import datetime, timezone

    from fastapi.encoders import jsonable_encoder

    from traininglogs.agent.card_edits import CardEditError, apply_card_edits, apply_card_op
    from traininglogs.agent.schemas import TrainingLogLLMExtract
    from traininglogs.agent.validation_card_builder import ValidationCardBuilder
    from traininglogs.db.fetch import get_extraction

    stored = get_extraction(conn, extraction_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="Extraction not found")

    extract_dict = body.extract if body.extract is not None else stored["extract"]
    current_extract = TrainingLogLLMExtract.model_validate(extract_dict)

    created_path = None
    try:
        if body.op is not None:
            updated_extract, edits, created_path = apply_card_op(current_extract, body.op)
        else:
            updated_extract, edits = apply_card_edits(current_extract, body.edits)
    except CardEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    correction = {
        "at": datetime.now(timezone.utc).isoformat(),
        "source": "manual",
        **({"op": body.op.op, "path": body.op.path} if body.op is not None else {}),
        "edits": [e.model_dump(mode="json") for e in edits],
    }
    card = ValidationCardBuilder().build(updated_extract)
    return CorrectOut(
        extract=updated_extract.model_dump(mode="json"),
        card=jsonable_encoder(card),
        correction=correction,
        created_path=created_path,
    )


# ---- programs, workouts and pinned notes ----
# Every change to a program or one of its workouts returns the whole program, so the client
# replaces what it shows with one reply.

def _program_or_404(conn, program_id: str) -> dict:
    from traininglogs.db.programs import get_program

    program = get_program(conn, program_id)
    if program is None:
        raise HTTPException(status_code=404, detail="Program not found")
    return program


def _workout_program_or_404(conn, workout_id: str) -> str:
    from traininglogs.db.programs import workout_program_id

    program_id = workout_program_id(conn, workout_id)
    if program_id is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    return program_id


@app.get("/programs", response_model=list[ProgramOut])
def programs_list(conn=Depends(_db), _=Depends(_auth)):
    from traininglogs.db.programs import list_programs

    return list_programs(conn)


@app.post("/programs", response_model=ProgramOut, status_code=201)
def programs_create(body: ProgramIn, conn=Depends(_db), _=Depends(_auth)):
    from traininglogs.db.programs import create_program

    return _program_or_404(conn, create_program(conn, body.name.strip()))


@app.get("/programs/{program_id}", response_model=ProgramOut)
def programs_get(program_id: str, conn=Depends(_db), _=Depends(_auth)):
    return _program_or_404(conn, program_id)


@app.patch("/programs/{program_id}", response_model=ProgramOut)
def programs_update(program_id: str, body: ProgramPatch, conn=Depends(_db), _=Depends(_auth)):
    from traininglogs.db.programs import update_program

    name = body.name.strip() if body.name else None
    if not update_program(conn, program_id, name=name, deload_after_days=body.deload_after_days):
        raise HTTPException(status_code=404, detail="Program not found")
    return _program_or_404(conn, program_id)


@app.post("/programs/{program_id}/follow", response_model=ProgramOut)
def programs_follow(program_id: str, conn=Depends(_db), _=Depends(_auth)):
    """Follow this program; any other followed program stops being followed."""
    from datetime import date

    from traininglogs.db.programs import follow_program

    if not follow_program(conn, program_id, date.today()):
        raise HTTPException(status_code=404, detail="Program not found")
    return _program_or_404(conn, program_id)


@app.post("/programs/{program_id}/unfollow", response_model=ProgramOut)
def programs_unfollow(program_id: str, conn=Depends(_db), _=Depends(_auth)):
    from traininglogs.db.programs import unfollow_program

    if not unfollow_program(conn, program_id):
        raise HTTPException(status_code=404, detail="Program not found")
    return _program_or_404(conn, program_id)


@app.delete("/programs/{program_id}", status_code=204)
def programs_archive(program_id: str, conn=Depends(_db), _=Depends(_auth)):
    """Removes the program from the app. It is marked archived, not deleted."""
    from traininglogs.db.programs import archive_program

    if not archive_program(conn, program_id):
        raise HTTPException(status_code=404, detail="Program not found")


@app.post("/programs/{program_id}/workouts", response_model=ProgramOut, status_code=201)
def workouts_add(program_id: str, body: WorkoutIn, conn=Depends(_db), _=Depends(_auth)):
    from traininglogs.db.programs import add_workout

    name = body.name.strip() if body.name and body.name.strip() else None
    if add_workout(conn, program_id, name) is None:
        raise HTTPException(status_code=404, detail="Program not found")
    return _program_or_404(conn, program_id)


@app.put("/programs/{program_id}/workout-order", response_model=ProgramOut)
def workouts_reorder(program_id: str, body: WorkoutOrderIn, conn=Depends(_db), _=Depends(_auth)):
    from traininglogs.db.programs import reorder_workouts

    _program_or_404(conn, program_id)
    if not reorder_workouts(conn, program_id, body.workout_ids):
        raise HTTPException(status_code=422, detail="List every workout of the program once each.")
    return _program_or_404(conn, program_id)


@app.patch("/workouts/{workout_id}", response_model=ProgramOut)
def workouts_rename(workout_id: str, body: WorkoutIn, conn=Depends(_db), _=Depends(_auth)):
    """Renames a workout; an empty or null name clears it, so it shows as its number."""
    from traininglogs.db.programs import rename_workout

    program_id = _workout_program_or_404(conn, workout_id)
    rename_workout(conn, workout_id, body.name.strip() if body.name and body.name.strip() else None)
    return _program_or_404(conn, program_id)


@app.put("/workouts/{workout_id}/exercises", response_model=ProgramOut)
def workouts_set_exercises(workout_id: str, body: WorkoutExercisesIn, conn=Depends(_db), _=Depends(_auth)):
    """Replaces the workout's plan with these exercises, in this order."""
    from traininglogs.db.programs import set_workout_exercises

    program_id = _workout_program_or_404(conn, workout_id)
    set_workout_exercises(conn, workout_id, [e.model_dump() for e in body.exercises])
    return _program_or_404(conn, program_id)


@app.delete("/workouts/{workout_id}", response_model=ProgramOut)
def workouts_archive(workout_id: str, conn=Depends(_db), _=Depends(_auth)):
    """Removes a workout from its program (marked archived); the rest are renumbered."""
    from traininglogs.db.programs import archive_workout

    program_id = _workout_program_or_404(conn, workout_id)
    archive_workout(conn, workout_id)
    return _program_or_404(conn, program_id)


@app.get("/pins", response_model=list[PinOut])
def pins_list(conn=Depends(_db), _=Depends(_auth)):
    from traininglogs.db.programs import list_pins

    return list_pins(conn)


@app.put("/pins/{exercise_name}", response_model=list[PinOut])
def pins_set(exercise_name: str, body: PinIn, conn=Depends(_db), _=Depends(_auth)):
    """Pins a note to an exercise, replacing any note already pinned to it."""
    from traininglogs.db.programs import list_pins, set_pin

    set_pin(conn, exercise_name, body.note.strip())
    return list_pins(conn)


@app.delete("/pins/{exercise_name}", status_code=204)
def pins_remove(exercise_name: str, conn=Depends(_db), _=Depends(_auth)):
    from traininglogs.db.programs import remove_pin

    if not remove_pin(conn, exercise_name):
        raise HTTPException(status_code=404, detail="No note pinned to that exercise")


class _NoCacheStaticFiles(StaticFiles):
    """The web UI, revalidated on every load. A browser serving a cached app.js after a deploy
    is how an old UI kept appearing locally (and cost two paid extractions)."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


# Serve web/ from the same origin as the API -- one deploy, no CORS. Mounted last so every API
# route above takes precedence. WEB_DIR is set in the container image; locally the repo's web/
# is found from the working directory.
# The React app (frontend/, built to frontend/dist) is served at /app/ until it replaces web/ in
# step 8 of react-plan.md. It must be mounted before "/", which would otherwise catch /app/ too.
_app_dir = Path(os.environ.get("APP_DIR", "frontend/dist"))
if _app_dir.is_dir():
    app.mount("/app", _NoCacheStaticFiles(directory=_app_dir, html=True), name="app")

_web_dir = Path(os.environ.get("WEB_DIR", "web"))
if _web_dir.is_dir():
    app.mount("/", _NoCacheStaticFiles(directory=_web_dir, html=True), name="web")
