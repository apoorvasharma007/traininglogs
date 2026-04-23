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
    user_name            TEXT
);

CREATE TABLE IF NOT EXISTS exercises (
    id              SERIAL PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    number          INT NOT NULL,
    name            TEXT NOT NULL,
    notes           TEXT,
    warmup_notes    TEXT,
    form_cues       TEXT[],
    goal_weight_kg  NUMERIC,
    goal_sets       INT,
    goal_rep_min    INT,
    goal_rep_max    INT,
    goal_rest_min   INT
);

CREATE TABLE IF NOT EXISTS working_sets (
    id                SERIAL PRIMARY KEY,
    exercise_id       INT NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    number            INT NOT NULL,
    weight_kg         NUMERIC,
    reps_full         INT,
    reps_partial      INT,
    rpe               NUMERIC,
    rep_quality       TEXT,
    rest_minutes      NUMERIC,
    notes             TEXT,
    failure_technique JSONB
);

CREATE TABLE IF NOT EXISTS warmup_sets (
    id          SERIAL PRIMARY KEY,
    exercise_id INT NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    number      INT NOT NULL,
    weight_kg   NUMERIC,
    rep_count   INT,
    notes       TEXT
);
