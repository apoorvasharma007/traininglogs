-- ---------------------------------------------------------------------------
-- Capture and interpretation layers.
--
-- `raw_inputs` is what the person actually produced -- the markdown they typed, and later the
-- text off a photograph or a speech transcript. It is never edited. Everything downstream can
-- be rebuilt from it, which is the point: an extraction is a *derived* artifact, and deriving
-- it again with a better model or prompt must not require the person to write anything twice.
--
-- `extractions` is one attempt at reading a raw input. Several may exist for the same input --
-- different model, different prompt, a re-run after a fix -- so this is deliberately not a
-- one-to-one relationship. The extract is stored whole, as sent, including the fields the
-- normalized tables drop: `uncertain_fields` (what the model was unsure of) and `warnings`
-- (what the checks found). Those were being computed and then discarded, which threw away the
-- only signal about how much to trust a row.
--
-- Every child table's foreign key cascades on delete -- deleting a session removes its
-- exercises, sets, and warmups with it; deleting a raw_input removes its extractions.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS raw_inputs (
    id          TEXT PRIMARY KEY,
    content     TEXT NOT NULL,
    -- What kind of capture this was. Markdown today; the other two are why this table exists.
    source_kind TEXT NOT NULL,
    -- Where it came from, when there is a where. Null for pasted or spoken input.
    source_file TEXT,
    -- sha256 of `content`. Lets a re-run recognise text it has already seen without comparing
    -- whole documents, and proves the row was not altered after the fact.
    checksum    TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT raw_inputs_source_kind_check
        CHECK (source_kind IN ('markdown', 'photo', 'speech', 'repeat'))
);

-- 'repeat' (a session started from a past one, ingest/repeat.py) was added after raw_inputs
-- existed in real databases, and CREATE TABLE IF NOT EXISTS doesn't touch an existing table's
-- constraints -- so the check is re-stated here, idempotently, for those databases too. Unlike
-- the other three kinds, a repeat's content is a line the app wrote, not a workout to read:
-- anything that re-reads raw inputs with a model must skip it.
ALTER TABLE raw_inputs
    DROP CONSTRAINT IF EXISTS raw_inputs_source_kind_check,
    ADD CONSTRAINT raw_inputs_source_kind_check
        CHECK (source_kind IN ('markdown', 'photo', 'speech', 'repeat'));

CREATE TABLE IF NOT EXISTS extractions (
    id               TEXT PRIMARY KEY,
    raw_input_id     TEXT NOT NULL REFERENCES raw_inputs(id) ON DELETE CASCADE,
    -- Which model and which prompts produced this. Without both, a change in accuracy months
    -- from now is unattributable.
    model            TEXT NOT NULL,
    prompt_version   TEXT NOT NULL,
    extract          JSONB NOT NULL,
    uncertain_fields TEXT[] NOT NULL DEFAULT '{}',
    warnings         TEXT[] NOT NULL DEFAULT '{}',
    status           TEXT NOT NULL DEFAULT 'pending',
    -- Appended to, never rewritten. `extract` stays the model's own reading; each entry here is
    -- one thing the person said and the edits it produced. Keeps three facts permanently
    -- separable -- what the model said, what the person changed, what was stored -- and makes
    -- "which fields do I correct most often?" a query rather than a guess.
    corrections      JSONB NOT NULL DEFAULT '[]',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed_at     TIMESTAMPTZ,
    CONSTRAINT extractions_status_check
        CHECK (status IN ('pending', 'confirmed', 'rejected'))
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id           TEXT PRIMARY KEY,
    date                 DATE NOT NULL,
    program              TEXT,
    program_author       TEXT,
    program_length_weeks INT,
    phase                INT,
    week                 INT,
    is_deload_week       BOOLEAN,
    focus                TEXT,
    duration_minutes     INT,
    weight_unit          TEXT NOT NULL DEFAULT 'kg',
    user_id              TEXT,
    user_name            TEXT,
    source_file          TEXT,
    notes                TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Added after `sessions` already existed in real databases, so it is an ALTER rather than a
-- column in the CREATE above: `CREATE TABLE IF NOT EXISTS` does nothing to a table that is
-- already there, and would silently skip the new column. Nullable because sessions written
-- before this existed have no extraction to point at, and because the rules parser has none.
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS extraction_id TEXT REFERENCES extractions(id);
-- For databases where `extractions` was created before this column existed.
ALTER TABLE extractions ADD COLUMN IF NOT EXISTS corrections JSONB NOT NULL DEFAULT '[]';

CREATE TABLE IF NOT EXISTS warmups (
    id               SERIAL PRIMARY KEY,
    session_id       TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    number           INT NOT NULL,
    name             TEXT NOT NULL,
    reps             INT,
    duration_seconds INT,
    notes            TEXT
);

CREATE TABLE IF NOT EXISTS cooldowns (
    id               SERIAL PRIMARY KEY,
    session_id       TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    number           INT NOT NULL,
    name             TEXT NOT NULL,
    reps             INT,
    duration_seconds INT,
    notes            TEXT
);

CREATE TABLE IF NOT EXISTS exercises (
    id               SERIAL PRIMARY KEY,
    session_id       TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    number           INT NOT NULL,
    name             TEXT NOT NULL,
    tags             TEXT[],
    modality         TEXT,
    movement_pattern TEXT[],
    notes            TEXT,
    warmup_notes     TEXT,
    form_cues        TEXT[],
    goal_weight_kg             NUMERIC,
    goal_sets                  INT,
    goal_rep_min               INT,
    goal_rep_max               INT,
    goal_rest_min              INT,
    goal_rest_seconds          INT,
    goal_distance_meters       NUMERIC,
    goal_target_duration_sec   INT,
    target_muscle_groups       TEXT[],
    rep_tempo                  TEXT
);

CREATE TABLE IF NOT EXISTS working_sets (
    id                  SERIAL PRIMARY KEY,
    exercise_id         INT NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    number              INT NOT NULL,
    weight_kg           NUMERIC,
    reps_full           INT,
    reps_partial        INT,
    left_reps_full      INT,
    left_reps_partial   INT,
    right_reps_full     INT,
    right_reps_partial  INT,
    rpe                 NUMERIC,
    rep_quality         TEXT,
    rest_minutes        NUMERIC,
    rest_seconds        INT,
    duration_seconds    INT,
    distance_meters     NUMERIC,
    heart_rate_bpm      INT,
    notes               TEXT,
    failure_technique   JSONB
);

CREATE TABLE IF NOT EXISTS warmup_sets (
    id          SERIAL PRIMARY KEY,
    exercise_id INT NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    number      INT NOT NULL,
    weight_kg   NUMERIC,
    rep_count   INT,
    notes       TEXT
);

-- ---------------------------------------------------------------------------
-- One row per LLM call site (segment/shell/worker/correction), not per raw HTTP attempt --
-- `attempts` says how many of those an extract() call needed, so a retry storm is visible as a
-- number instead of showing up only as inflated tokens. Makes cost a SQL query instead of
-- something read out of console output (roadmap D4). `raw_payload` is the last tool-call
-- payload seen even when `failed` is set, so a validation rejection does not also cost the
-- response that triggered it (D6).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS llm_calls (
    id           SERIAL PRIMARY KEY,
    raw_input_id TEXT NOT NULL REFERENCES raw_inputs(id) ON DELETE CASCADE,
    step         TEXT NOT NULL,
    model        TEXT NOT NULL,
    attempts     INT NOT NULL,
    input_tokens  INT NOT NULL DEFAULT 0,
    output_tokens INT NOT NULL DEFAULT 0,
    cost_usd     NUMERIC NOT NULL DEFAULT 0,
    ms           INT NOT NULL,
    -- Always false today -- prompt caching was measured and dropped (roadmap B9). Reserved so a
    -- future caching decision doesn't need a new column, just a value.
    cached       BOOLEAN NOT NULL DEFAULT false,
    failed       TEXT,
    raw_payload  JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Finding earlier captures of the same text, and every attempt at reading one input.
CREATE INDEX IF NOT EXISTS idx_raw_inputs_checksum      ON raw_inputs(checksum);
CREATE INDEX IF NOT EXISTS idx_extractions_raw_input_id ON extractions(raw_input_id);
CREATE INDEX IF NOT EXISTS idx_llm_calls_raw_input_id   ON llm_calls(raw_input_id);

CREATE INDEX IF NOT EXISTS idx_warmups_session_id   ON warmups(session_id);
CREATE INDEX IF NOT EXISTS idx_cooldowns_session_id ON cooldowns(session_id);
CREATE INDEX IF NOT EXISTS idx_exercises_session_id         ON exercises(session_id);
CREATE INDEX IF NOT EXISTS idx_working_sets_exercise_id     ON working_sets(exercise_id);

-- Programs (Phase 8). A program is workouts in order; after the last one it starts again at 1.
-- Removing a program or workout marks it archived, so sessions that point at it keep the link.
CREATE TABLE IF NOT EXISTS programs (
    id                TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    deload_after_days INT  NOT NULL DEFAULT 28 CHECK (deload_after_days > 0),
    following         BOOLEAN NOT NULL DEFAULT false,
    -- The deload count starts here, or at the last deload session, whichever is later.
    following_since   DATE,
    archived_at       TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- At most one program is followed at a time.
CREATE UNIQUE INDEX IF NOT EXISTS programs_one_followed ON programs (following) WHERE following;

-- Workout 1, 2, 3 of a program. The name is optional ("Push").
CREATE TABLE IF NOT EXISTS program_workouts (
    id          TEXT PRIMARY KEY,
    program_id  TEXT NOT NULL REFERENCES programs(id),
    position    INT  NOT NULL CHECK (position > 0),
    name        TEXT,
    archived_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The plan inside a workout. No weights: a session takes them from the last time.
CREATE TABLE IF NOT EXISTS program_workout_exercises (
    id           TEXT PRIMARY KEY,
    workout_id   TEXT NOT NULL REFERENCES program_workouts(id) ON DELETE CASCADE,
    position     INT  NOT NULL CHECK (position > 0),
    name         TEXT NOT NULL,
    warmup_sets  INT  NOT NULL DEFAULT 0 CHECK (warmup_sets >= 0),
    working_sets INT  NOT NULL DEFAULT 1 CHECK (working_sets >= 0),
    target_reps  INT  CHECK (target_reps > 0),
    -- "1 × max": as many reps as you can.
    amrap        BOOLEAN NOT NULL DEFAULT false
);

-- A note pinned to an exercise shows in every later session of it. Matched ignoring case.
CREATE TABLE IF NOT EXISTS exercise_pins (
    name_key  TEXT PRIMARY KEY,
    note      TEXT NOT NULL,
    pinned_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Which planned workout a session came from; empty for blank workouts and older sessions.
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS program_workout_id TEXT REFERENCES program_workouts(id);

CREATE INDEX IF NOT EXISTS idx_program_workouts_program_id ON program_workouts(program_id);
CREATE INDEX IF NOT EXISTS idx_program_workout_exercises_workout_id ON program_workout_exercises(workout_id);
CREATE INDEX IF NOT EXISTS idx_sessions_program_workout_id ON sessions(program_workout_id);
