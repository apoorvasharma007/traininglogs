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
        CHECK (source_kind IN ('markdown', 'photo', 'speech'))
);

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

-- Finding earlier captures of the same text, and every attempt at reading one input.
CREATE INDEX IF NOT EXISTS idx_raw_inputs_checksum      ON raw_inputs(checksum);
CREATE INDEX IF NOT EXISTS idx_extractions_raw_input_id ON extractions(raw_input_id);

CREATE INDEX IF NOT EXISTS idx_warmups_session_id   ON warmups(session_id);
CREATE INDEX IF NOT EXISTS idx_cooldowns_session_id ON cooldowns(session_id);
CREATE INDEX IF NOT EXISTS idx_exercises_session_id         ON exercises(session_id);
CREATE INDEX IF NOT EXISTS idx_working_sets_exercise_id     ON working_sets(exercise_id);
