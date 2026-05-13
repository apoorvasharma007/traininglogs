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
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

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

CREATE INDEX IF NOT EXISTS idx_warmups_session_id   ON warmups(session_id);
CREATE INDEX IF NOT EXISTS idx_cooldowns_session_id ON cooldowns(session_id);
CREATE INDEX IF NOT EXISTS idx_exercises_session_id         ON exercises(session_id);
CREATE INDEX IF NOT EXISTS idx_working_sets_exercise_id     ON working_sets(exercise_id);
