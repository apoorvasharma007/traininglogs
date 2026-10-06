import os
import time
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import psycopg2
from psycopg2.pool import SimpleConnectionPool

from traininglogs.api.auth import bearer, user_for, verify
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
    LastExercise,
    LiftDetail,
    LiftsOut,
    ManualSessionIn,
    ProgramIn,
    ProgramOut,
    ProgramPatch,
    ProgramTemplate,
    SessionDetail,
    SessionSaved,
    SessionSummary,
    WorkoutExercisesIn,
    WorkoutIn,
    WorkoutMovementsIn,
    WorkoutOrderIn,
)

load_dotenv()

ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "").split(",")

_pool: SimpleConnectionPool | None = None


def _get_pool() -> SimpleConnectionPool:
    global _pool
    if _pool is None:
        db_url = os.environ["DATABASE_URL"]
        # Keepalives stop an idle connection from being dropped along the way; the name lets the
        # tests find this pool's connections in pg_stat_activity.
        _pool = SimpleConnectionPool(
            minconn=1, maxconn=10, dsn=db_url, application_name="traininglogs-api",
            keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3,
        )
    return _pool


# A connection idle longer than this is checked before use; Supabase closes idle ones.
IDLE_CHECK_SECONDS = 60.0
_last_used: dict[int, float] = {}


def _live_connection(pool: SimpleConnectionPool):
    """A connection from the pool that the server hasn't closed. Reusing a closed one made every
    request fail until a restart. One that sat idle gets a `SELECT 1` first; a failure replaces
    it. Connections in steady use skip the check."""
    for _ in range(pool.maxconn + 1):
        conn = pool.getconn()
        idle = time.monotonic() - _last_used.get(id(conn), 0.0)
        try:
            if not conn.closed:
                if idle > IDLE_CHECK_SECONDS:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                    conn.rollback()
                return conn
        except psycopg2.Error:
            pass
        _last_used.pop(id(conn), None)
        pool.putconn(conn, close=True)
    raise HTTPException(status_code=503, detail="Database unavailable (503). Try again in a minute.")


def _db():
    pool = _get_pool()
    conn = _live_connection(pool)
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
        if conn.closed:
            # Lost mid-request: don't hand a dead connection to the next one.
            pool.putconn(conn, close=True)
        else:
            try:
                conn.rollback()
                _last_used[id(conn)] = time.monotonic()
                pool.putconn(conn)
            except psycopg2.Error:
                pool.putconn(conn, close=True)


def _user(conn=Depends(_db), token: str = Depends(bearer)) -> str:
    """The signed-in person's users.id, from the pass on the request (api/auth.py). Every
    endpoint but the app's own files needs it; nothing the phone sends can name another user."""
    return user_for(conn, verify(token))


@asynccontextmanager
async def lifespan(app: FastAPI):
    missing = [name for name in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY") if not os.environ.get(name)]
    if missing:
        print(
            f"ERROR: {' and '.join(missing)} not set: sign-in goes through that Supabase project. "
            "Set them in .env before starting the server.",
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
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/config")
def public_config():
    """What the app needs before anyone signs in: this environment's Supabase project and its
    publishable key. Both are public by design (the key can do only what row-level security
    allows, which is nothing); one build of the app then works in every environment."""
    return {"supabase_url": os.environ["SUPABASE_URL"], "supabase_publishable_key": os.environ["SUPABASE_PUBLISHABLE_KEY"]}


@app.get("/sessions", response_model=list[SessionSummary])
def list_sessions(
    phase: int | None = Query(None),
    week: int | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    limit: int | None = Query(None, ge=1, le=500),
    conn=Depends(_db),
    user: str = Depends(_user),
):
    return get_sessions(conn, user, phase=phase, week=week, from_date=from_date, to_date=to_date, limit=limit)


NO_WORKOUT = "That workout doesn't exist or was removed."


def _check_workout(conn, user: str, workout_id: str | None) -> None:
    """422 when a request names a workout the person doesn't have."""
    from traininglogs.db.programs import workout_program_id

    if workout_id is not None and (not _is_id(workout_id) or workout_program_id(conn, user, workout_id) is None):
        raise HTTPException(status_code=422, detail=NO_WORKOUT)


@app.post("/sessions", response_model=SessionSaved, status_code=201)
def save_session(body: ManualSessionIn, response: Response, conn=Depends(_db), user: str = Depends(_user)):
    """Saves a session logged in the app, with no AI. Sending the same `client_id` again returns the
    session already saved, with 200 instead of 201."""
    from traininglogs.ingest.confirm import AlreadySaved
    from traininglogs.ingest.manual import save_manual_session

    _check_workout(conn, user, body.program_workout_id)
    try:
        session_id, created = save_manual_session(conn, user, body.model_dump(mode="json"))
    except AlreadySaved:
        raise HTTPException(status_code=409, detail="This session is already saved. Find it in History.")
    if not created:
        response.status_code = 200
    return SessionSaved(session_id=session_id, created=created)


@app.get("/exercises/last", response_model=list[LastExercise])
def last_exercises(name: list[str] = Query(default=[]), conn=Depends(_db), user: str = Depends(_user)):
    """Last time for each named exercise: the latest session that had it, from any program."""
    from traininglogs.db.fetch import get_last_exercises

    return get_last_exercises(conn, name, user)


@app.get("/sessions/{session_id}", response_model=SessionDetail)
def session_detail(session_id: str, conn=Depends(_db), user: str = Depends(_user)):
    session = get_session(conn, user, session_id) if _is_id(session_id) else None
    if session is None:
        raise HTTPException(status_code=404, detail="Couldn't find this session.")
    return session


def _is_id(value: str) -> bool:
    """Whether a path's id could be one of ours, so a malformed one is a plain 404, not a database
    error."""
    import uuid

    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


@app.get("/progress/lifts", response_model=LiftsOut)
def progress_lifts(conn=Depends(_db), user: str = Depends(_user)):
    """Key lifts, then other lifts trained in 3 or more sessions: each with its latest and best
    estimated max (or best reps at bodyweight), and the trend over the last 4 weeks."""
    from traininglogs.analytics.progress import lift_summaries
    from traininglogs.db.fetch import get_working_set_rows
    from traininglogs.db.programs import utc_today

    return lift_summaries(get_working_set_rows(conn, user), utc_today())


@app.get("/progress/lifts/{name}", response_model=LiftDetail)
def progress_lift(name: str, conn=Depends(_db), user: str = Depends(_user)):
    """One lift's sessions, oldest first: the value, the set behind it, records and goal."""
    from traininglogs.analytics.progress import lift_detail
    from traininglogs.db.fetch import get_working_set_rows
    from traininglogs.db.programs import utc_today

    detail = lift_detail(get_working_set_rows(conn, user), name, utc_today())
    if detail is None:
        raise HTTPException(status_code=404, detail="No lift with that name")
    return detail


@app.get("/exercises/{name}/history", response_model=list[ExerciseHistoryRow])
def exercise_history(name: str, conn=Depends(_db), user: str = Depends(_user)):
    rows = get_exercise_history(conn, name, user)
    if not rows:
        raise HTTPException(status_code=404, detail="No sessions with this exercise yet.")
    return rows


@app.post("/inputs", response_model=CaptureOut)
def create_input(body: CaptureIn, response: Response, conn=Depends(_db), user: str = Depends(_user)):
    """Store the note, then have the AI read it into a confirmation card.

    The note is saved before the AI is asked, so a failed reading still leaves `raw_input_id` in
    the answer: nothing is lost, and reading it again uses the same note.
    """
    from traininglogs.agent.providers import AnthropicProvider
    from traininglogs.db.insert import insert_input
    from traininglogs.ingest.extract import extract

    input_id = insert_input(conn, user, body.content, kind=body.source_kind, source=body.source_file)
    try:
        provider = AnthropicProvider()
        card_id = extract(conn, user, input_id, body.date, provider=provider, model=provider.model)
    except Exception as exc:
        print(f"Reading note {input_id} failed: {exc}", flush=True)
        response.status_code = 502
        return CaptureOut(
            raw_input_id=input_id,
            error="Couldn't read your note. It's saved, so nothing is lost. Try again in a minute.",
        )
    response.status_code = 201
    return CaptureOut(raw_input_id=input_id, extraction_id=card_id)


NO_NOTE = "Couldn't find this note."


def _card_or_404(conn, user: str, card_id: str) -> dict:
    from traininglogs.db.fetch import get_card

    card = get_card(conn, user, card_id) if _is_id(card_id) else None
    if card is None:
        raise HTTPException(status_code=404, detail=NO_NOTE)
    return card


@app.get("/extractions/{extraction_id}")
def get_extraction_card(extraction_id: str, conn=Depends(_db), user: str = Depends(_user)):
    """The confirmation card for a note, as JSON."""
    from fastapi.encoders import jsonable_encoder

    from traininglogs.agent.schemas import TrainingLogLLMExtract
    from traininglogs.agent.validation_card_builder import ValidationCardBuilder

    card = _card_or_404(conn, user, extraction_id)
    return jsonable_encoder(ValidationCardBuilder().build(TrainingLogLLMExtract.model_validate(card["extract"])))


@app.post("/extractions/{extraction_id}/confirm", response_model=ConfirmOut)
def confirm_extraction_endpoint(
    extraction_id: str,
    response: Response,
    body: ConfirmIn = ConfirmIn(),
    conn=Depends(_db),
    user: str = Depends(_user),
):
    """Save the card as a session. `body.extract` carries the result of any fixes; omitted, the
    card's own reading is saved as it is."""
    from traininglogs.agent.schemas import TrainingLogLLMExtract
    from traininglogs.ingest.confirm import AlreadySaved, confirm

    card = _card_or_404(conn, user, extraction_id)
    _check_workout(conn, user, body.program_workout_id)
    final_extract = TrainingLogLLMExtract.model_validate(body.extract if body.extract is not None else card["extract"])
    try:
        session_id = confirm(
            conn, user, extraction_id, final_extract, corrections=body.corrections,
            program_workout_id=body.program_workout_id,
        )
    except AlreadySaved:
        raise HTTPException(status_code=409, detail="This note is already saved as a session. Find it in History.")
    response.status_code = 201
    return ConfirmOut(session_id=session_id)


@app.post("/extractions/{extraction_id}/correct", response_model=CorrectOut)
def correct_extraction(extraction_id: str, body: CorrectIn, conn=Depends(_db), user: str = Depends(_user)):
    """Apply one typed fix with the AI and hand back the result, keeping nothing on the server:
    `body.extract` (the previous answer's `extract`) carries the state between fixes; the card's own
    reading is the starting point on the first."""
    from datetime import datetime, timezone

    from fastapi.encoders import jsonable_encoder

    from traininglogs.agent.llm_extract_validator import CorrectionRejected, LLMExtractValidator
    from traininglogs.agent.patch import PatchError
    from traininglogs.agent.providers import AnthropicProvider
    from traininglogs.agent.schemas import LLMParserError, TrainingLogLLMExtract
    from traininglogs.agent.validation_card_builder import ValidationCardBuilder
    from traininglogs.db.insert import insert_ai_calls

    card = _card_or_404(conn, user, extraction_id)
    current = TrainingLogLLMExtract.model_validate(body.extract if body.extract is not None else card["extract"])
    provider = AnthropicProvider()
    try:
        updated, edits = LLMExtractValidator(provider).apply_correction(current, body.instruction)
    except PatchError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except CorrectionRejected as exc:
        # The full technical reason goes to the server log; the person gets the plain one.
        print(f"Correction rejected for {extraction_id}: {exc}", flush=True)
        raise HTTPException(status_code=422, detail=exc.plain)
    except LLMParserError as exc:
        print(f"Correction failed for {extraction_id}: {exc}", flush=True)
        raise HTTPException(status_code=502, detail="The request failed. Try again in a minute.")
    finally:
        # Kept whether the fix worked or not: a failed fix still cost money.
        insert_ai_calls(conn, user, card["input_id"], provider.calls)

    return CorrectOut(
        extract=updated.model_dump(mode="json"),
        card=jsonable_encoder(ValidationCardBuilder().build(updated)),
        correction={
            "at": datetime.now(timezone.utc).isoformat(),
            "source": "ai",
            "instruction": body.instruction,
            "edits": [e.model_dump(mode="json") for e in edits],
        },
    )


@app.post("/extractions/{extraction_id}/edit", response_model=CorrectOut)
def edit_extraction(extraction_id: str, body: EditIn, conn=Depends(_db), user: str = Depends(_user)):
    """Apply values changed directly on the card, or add or remove one line, with no AI. Kept
    nothing on the server, like /correct, and answered in the same shape."""
    from datetime import datetime, timezone

    from fastapi.encoders import jsonable_encoder

    from traininglogs.agent.card_edits import CardEditError, apply_card_edits, apply_card_op
    from traininglogs.agent.schemas import TrainingLogLLMExtract
    from traininglogs.agent.validation_card_builder import ValidationCardBuilder

    card = _card_or_404(conn, user, extraction_id)
    current = TrainingLogLLMExtract.model_validate(body.extract if body.extract is not None else card["extract"])
    created_path = None
    try:
        if body.op is not None:
            updated, edits, created_path = apply_card_op(current, body.op)
        else:
            updated, edits = apply_card_edits(current, body.edits)
    except CardEditError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return CorrectOut(
        extract=updated.model_dump(mode="json"),
        card=jsonable_encoder(ValidationCardBuilder().build(updated)),
        correction={
            "at": datetime.now(timezone.utc).isoformat(),
            "source": "manual",
            **({"op": body.op.op, "path": body.op.path} if body.op is not None else {}),
            "edits": [e.model_dump(mode="json") for e in edits],
        },
        created_path=created_path,
    )


# ---- programs and workouts ----
# Every change to a program or one of its workouts returns the whole program, so the app replaces
# what it shows with one answer. Someone else's program or workout is "not found".

NO_PROGRAM = "Program not found"
NO_WORKOUT_HERE = "Workout not found"


def _program_or_404(conn, user: str, program_id: str) -> dict:
    from traininglogs.db.programs import get_program

    program = get_program(conn, user, program_id) if _is_id(program_id) else None
    if program is None:
        raise HTTPException(status_code=404, detail=NO_PROGRAM)
    return program


def _workout_program_or_404(conn, user: str, workout_id: str) -> str:
    from traininglogs.db.programs import workout_program_id

    program_id = workout_program_id(conn, user, workout_id) if _is_id(workout_id) else None
    if program_id is None:
        raise HTTPException(status_code=404, detail=NO_WORKOUT_HERE)
    return program_id


def _done(found: bool, missing: str = NO_PROGRAM) -> None:
    if not found:
        raise HTTPException(status_code=404, detail=missing)


@app.get("/programs", response_model=list[ProgramOut])
def programs_list(conn=Depends(_db), user: str = Depends(_user)):
    from traininglogs.db.programs import list_programs

    return list_programs(conn, user)


@app.post("/programs", response_model=ProgramOut, status_code=201)
def programs_create(body: ProgramIn, conn=Depends(_db), user: str = Depends(_user)):
    from traininglogs.db.programs import create_program

    return _program_or_404(conn, user, create_program(conn, user, body.name.strip()))


@app.get("/templates", response_model=list[ProgramTemplate])
def templates_list(user: str = Depends(_user)):
    """Ready-made programs to copy from."""
    from traininglogs.program_templates import TEMPLATES

    return TEMPLATES


@app.post("/templates/{template_id}/copy", response_model=ProgramOut, status_code=201)
def templates_copy(template_id: str, conn=Depends(_db), user: str = Depends(_user)):
    """Adds a copy of the template to the person's programs. Not followed; copying twice gives two."""
    from traininglogs.db.programs import create_program
    from traininglogs.program_templates import get_template

    template = get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Couldn't find this template.")
    workouts = [w.model_dump() for w in template.workouts]
    return _program_or_404(conn, user, create_program(conn, user, template.name, workouts))


@app.get("/programs/{program_id}", response_model=ProgramOut)
def programs_get(program_id: str, conn=Depends(_db), user: str = Depends(_user)):
    return _program_or_404(conn, user, program_id)


@app.patch("/programs/{program_id}", response_model=ProgramOut)
def programs_update(program_id: str, body: ProgramPatch, conn=Depends(_db), user: str = Depends(_user)):
    from traininglogs.db.programs import update_program

    name = body.name.strip() if body.name else None
    _done(_is_id(program_id) and update_program(conn, user, program_id, name=name, deload_after_days=body.deload_after_days))
    return _program_or_404(conn, user, program_id)


@app.post("/programs/{program_id}/follow", response_model=ProgramOut)
def programs_follow(program_id: str, conn=Depends(_db), user: str = Depends(_user)):
    """Follow this program; the person's other followed program stops being followed."""
    from traininglogs.db.programs import follow_program

    _done(_is_id(program_id) and follow_program(conn, user, program_id))
    return _program_or_404(conn, user, program_id)


@app.post("/programs/{program_id}/unfollow", response_model=ProgramOut)
def programs_unfollow(program_id: str, conn=Depends(_db), user: str = Depends(_user)):
    from traininglogs.db.programs import unfollow_program

    _done(_is_id(program_id) and unfollow_program(conn, user, program_id))
    return _program_or_404(conn, user, program_id)


@app.delete("/programs/{program_id}", status_code=204)
def programs_archive(program_id: str, conn=Depends(_db), user: str = Depends(_user)):
    """Removes the program from the app. It is marked archived, not deleted."""
    from traininglogs.db.programs import archive_program

    _done(_is_id(program_id) and archive_program(conn, user, program_id))


@app.post("/programs/{program_id}/workouts", response_model=ProgramOut, status_code=201)
def workouts_add(program_id: str, body: WorkoutIn, conn=Depends(_db), user: str = Depends(_user)):
    from traininglogs.db.programs import add_workout

    name = body.name.strip() if body.name and body.name.strip() else None
    _done(_is_id(program_id) and add_workout(conn, user, program_id, name) is not None)
    return _program_or_404(conn, user, program_id)


@app.put("/programs/{program_id}/workout-order", response_model=ProgramOut)
def workouts_reorder(program_id: str, body: WorkoutOrderIn, conn=Depends(_db), user: str = Depends(_user)):
    from traininglogs.db.programs import reorder_workouts

    _program_or_404(conn, user, program_id)
    if not all(_is_id(w) for w in body.workout_ids) or not reorder_workouts(conn, user, program_id, body.workout_ids):
        raise HTTPException(status_code=422, detail="List every workout of the program once each.")
    return _program_or_404(conn, user, program_id)


@app.patch("/workouts/{workout_id}", response_model=ProgramOut)
def workouts_rename(workout_id: str, body: WorkoutIn, conn=Depends(_db), user: str = Depends(_user)):
    """Renames a workout; an empty or null name clears it, so it shows as its number."""
    from traininglogs.db.programs import rename_workout

    program_id = _workout_program_or_404(conn, user, workout_id)
    rename_workout(conn, user, workout_id, body.name.strip() if body.name and body.name.strip() else None)
    return _program_or_404(conn, user, program_id)


@app.put("/workouts/{workout_id}/exercises", response_model=ProgramOut)
def workouts_set_exercises(workout_id: str, body: WorkoutExercisesIn, conn=Depends(_db), user: str = Depends(_user)):
    """Replaces the workout's plan with these exercises, in this order."""
    from traininglogs.db.programs import set_workout_exercises

    program_id = _workout_program_or_404(conn, user, workout_id)
    set_workout_exercises(conn, user, workout_id, [e.model_dump() for e in body.exercises])
    return _program_or_404(conn, user, program_id)


@app.put("/workouts/{workout_id}/movements", response_model=ProgramOut)
def workouts_set_movements(workout_id: str, body: WorkoutMovementsIn, conn=Depends(_db), user: str = Depends(_user)):
    """Replaces the workout's warm-up and cool-down movements."""
    from traininglogs.db.programs import set_workout_movements

    program_id = _workout_program_or_404(conn, user, workout_id)
    set_workout_movements(
        conn, user, workout_id, [m.model_dump() for m in body.warmup], [m.model_dump() for m in body.cooldown]
    )
    return _program_or_404(conn, user, program_id)


@app.delete("/workouts/{workout_id}", response_model=ProgramOut)
def workouts_archive(workout_id: str, conn=Depends(_db), user: str = Depends(_user)):
    """Removes a workout from its program (marked archived); the rest are renumbered."""
    from traininglogs.db.programs import archive_workout

    program_id = _workout_program_or_404(conn, user, workout_id)
    archive_workout(conn, user, workout_id)
    return _program_or_404(conn, user, program_id)


class _NoCacheStaticFiles(StaticFiles):
    """The web UI, revalidated on every load. A browser serving a cached app.js after a deploy
    is how an old UI kept appearing locally (and cost two paid extractions)."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


@app.get("/app", include_in_schema=False)
@app.get("/app/", include_in_schema=False)
def old_app_address():
    """The app lived at /app/ while it was being built; old bookmarks land on / instead."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse("/", status_code=301)


# Serve the app (frontend/, built to frontend/dist) from the same origin as the API -- one deploy,
# no CORS. Mounted last so every API route above takes precedence. APP_DIR is set in the container
# image; locally `npm run build` in frontend/ makes frontend/dist.
_app_dir = Path(os.environ.get("APP_DIR", "frontend/dist"))
if _app_dir.is_dir():
    app.mount("/", _NoCacheStaticFiles(directory=_app_dir, html=True), name="app")
