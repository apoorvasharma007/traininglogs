-- ---------------------------------------------------------------------------
-- traininglogs' database. Design and reasons: db-redesign-plan.md (2026-10-06).
--
-- Every row's `id` is a time-ordered UUID (version 7) made by the code (db/ids.py); no id is
-- built from data or chosen by the phone. Every owned table has `user_id`, and each child points
-- at its parent by (user_id, parent id), so the database itself refuses a child owned by someone
-- other than its parent's owner, and any link to another person's row. Indexes on owned data lead
-- with user_id. Shared reference data (`exercises`) has no owner.
--
-- Row-level security is on everywhere with no policies (end of file): Supabase's automatic web
-- API can't reach any row. The server connects as the tables' owner, which Postgres exempts.
--
-- A database made before this design is converted by scripts/migrate_to_accounts.py, not here.
-- ---------------------------------------------------------------------------

-- People ---------------------------------------------------------------------

-- The private account. auth_id is the sign-in service's id for the person ("sub" in their pass);
-- data points at users.id instead, so changing sign-in services touches only this table.
CREATE TABLE IF NOT EXISTS users (
    id                   UUID PRIMARY KEY,
    auth_id              UUID NOT NULL UNIQUE,
    email                TEXT,
    status               TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disabled')),
    role                 TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('member', 'admin')),
    timezone             TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    weight_unit          TEXT NOT NULL DEFAULT 'kg' CHECK (weight_unit IN ('kg', 'lb')),
    ai_monthly_limit_usd NUMERIC NOT NULL DEFAULT 1.00 CHECK (ai_monthly_limit_usd >= 0),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at         TIMESTAMPTZ,
    -- "Delete my account" asked for: the data is removed after a grace period.
    deleted_at           TIMESTAMPTZ
);

-- The public-facing part, kept apart so a shared screen can never show account details.
CREATE TABLE IF NOT EXISTS profiles (
    user_id      UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    display_name TEXT,
    username     TEXT UNIQUE,
    avatar_url   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Exercises ------------------------------------------------------------------

-- The shared, curated list. Equipment and muscles live here, never on people's own names.
CREATE TABLE IF NOT EXISTS exercises (
    id          UUID PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    equipment   TEXT NOT NULL CHECK (equipment IN
                    ('barbell', 'dumbbell', 'kettlebell', 'band', 'cable', 'machine', 'bodyweight', 'other')),
    movement    TEXT,
    muscles     TEXT[] NOT NULL DEFAULT '{}',
    -- Other ways people write it, lower case, for linking automatically ("back squat", "squats").
    other_names TEXT[] NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A person's own exercise, in their words; made the first time they use a name. name_key is the
-- name ignoring case and extra spaces, so "Bench press" and "bench  Press" are one exercise.
CREATE TABLE IF NOT EXISTS user_exercises (
    id          UUID PRIMARY KEY,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    name        TEXT NOT NULL,
    name_key    TEXT NOT NULL GENERATED ALWAYS AS (lower(regexp_replace(btrim(name), '\s+', ' ', 'g'))) STORED,
    exercise_id UUID REFERENCES exercises(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, id),
    UNIQUE (user_id, name_key)
);

-- What people wrote or entered ------------------------------------------------

-- Exactly as given and never edited: a note (`text`, read by the AI) or a session logged in the
-- app (`manual`, stored as its JSON). client_id is the phone's id for an app session, so sending it
-- twice is recognised.
CREATE TABLE IF NOT EXISTS input_text (
    id         UUID PRIMARY KEY,
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    content    TEXT NOT NULL,
    kind       TEXT NOT NULL CHECK (kind IN ('text', 'manual')),
    client_id  TEXT,
    checksum   TEXT NOT NULL,
    -- Where it came from, when there is a where.
    source     TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, id),
    UNIQUE (user_id, client_id)
);

-- The AI's reading of a note, with the person's fixes, waiting for Confirm. `extract` stays the AI's
-- own reading; `corrections` is appended to, one entry per fix.
CREATE TABLE IF NOT EXISTS input_text_confirmation_cards (
    id               UUID PRIMARY KEY,
    user_id          UUID NOT NULL,
    input_id         UUID NOT NULL,
    model            TEXT NOT NULL,
    prompt_version   TEXT NOT NULL,
    extract          JSONB NOT NULL,
    uncertain_fields TEXT[] NOT NULL DEFAULT '{}',
    warnings         TEXT[] NOT NULL DEFAULT '{}',
    status           TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'rejected')),
    corrections      JSONB NOT NULL DEFAULT '[]',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    confirmed_at     TIMESTAMPTZ,
    UNIQUE (user_id, id),
    FOREIGN KEY (user_id, input_id) REFERENCES input_text(user_id, id) ON DELETE CASCADE
);

-- One paid AI call, kept whether it worked or not: a failed call still cost money.
CREATE TABLE IF NOT EXISTS ai_call_logs (
    id            UUID PRIMARY KEY,
    user_id       UUID NOT NULL,
    input_id      UUID NOT NULL,
    step          TEXT NOT NULL,
    model         TEXT NOT NULL,
    attempts      INT NOT NULL,
    input_tokens  INT NOT NULL DEFAULT 0,
    output_tokens INT NOT NULL DEFAULT 0,
    cost_usd      NUMERIC NOT NULL DEFAULT 0,
    ms            INT NOT NULL,
    cached        BOOLEAN NOT NULL DEFAULT false,
    failed        TEXT,
    raw_payload   JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (user_id, input_id) REFERENCES input_text(user_id, id) ON DELETE CASCADE
);

-- Programs -------------------------------------------------------------------

-- Workouts in order; after the last it starts again at the first. Removing one marks it archived,
-- so sessions that point at it keep the link.
CREATE TABLE IF NOT EXISTS programs (
    id                UUID PRIMARY KEY,
    user_id           UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    name              TEXT NOT NULL,
    deload_after_days INT NOT NULL DEFAULT 28 CHECK (deload_after_days > 0),
    following         BOOLEAN NOT NULL DEFAULT false,
    -- The deload count starts here, or at the last deload session, whichever is later.
    following_since   DATE,
    archived_at       TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, id)
);
-- Each person follows at most one program.
CREATE UNIQUE INDEX IF NOT EXISTS programs_one_followed_per_user ON programs (user_id) WHERE following;

CREATE TABLE IF NOT EXISTS program_workouts (
    id          UUID PRIMARY KEY,
    user_id     UUID NOT NULL,
    program_id  UUID NOT NULL,
    position    INT NOT NULL CHECK (position > 0),
    name        TEXT,
    -- Warm-up and cool-down movements, [{name, reps, duration_seconds}], copied into a session.
    warmup      JSONB NOT NULL DEFAULT '[]',
    cooldown    JSONB NOT NULL DEFAULT '[]',
    archived_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, id),
    FOREIGN KEY (user_id, program_id) REFERENCES programs(user_id, id)
);

-- The plan inside a workout. No weights: a session takes them from last time.
CREATE TABLE IF NOT EXISTS program_workout_exercises (
    id               UUID PRIMARY KEY,
    user_id          UUID NOT NULL,
    workout_id       UUID NOT NULL,
    position         INT NOT NULL CHECK (position > 0),
    user_exercise_id UUID NOT NULL,
    name             TEXT NOT NULL,
    warmup_sets      INT NOT NULL DEFAULT 0 CHECK (warmup_sets >= 0),
    working_sets     INT NOT NULL DEFAULT 1 CHECK (working_sets >= 0),
    target_reps      INT CHECK (target_reps > 0),
    -- As many reps as you can.
    amrap            BOOLEAN NOT NULL DEFAULT false,
    -- Other exercises that can take this one's place; a session can switch to one.
    alternatives     TEXT[] NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (user_id, workout_id) REFERENCES program_workouts(user_id, id) ON DELETE CASCADE,
    FOREIGN KEY (user_id, user_exercise_id) REFERENCES user_exercises(user_id, id)
);

-- Sessions -------------------------------------------------------------------

-- A saved session. dedup_key is the date and a fingerprint of the input's text, so the same note
-- confirmed twice for the same day is refused, per person. The markdown-era columns (program,
-- program_author, program_length_weeks, phase, week) are still read by the app.
CREATE TABLE IF NOT EXISTS workout_sessions (
    id                   UUID PRIMARY KEY,
    user_id              UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    date                 DATE NOT NULL,
    started_at           TIMESTAMPTZ,
    ended_at             TIMESTAMPTZ,
    duration_minutes     INT,
    focus                TEXT,
    notes                TEXT,
    dedup_key            TEXT NOT NULL,
    input_id             UUID NOT NULL,
    confirmation_card_id UUID,
    program_workout_id   UUID,
    program              TEXT,
    program_author       TEXT,
    program_length_weeks INT,
    phase                INT,
    week                 INT,
    is_deload_week       BOOLEAN,
    weight_unit          TEXT NOT NULL DEFAULT 'kg',
    source               TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, id),
    UNIQUE (user_id, dedup_key),
    FOREIGN KEY (user_id, input_id) REFERENCES input_text(user_id, id),
    FOREIGN KEY (user_id, confirmation_card_id) REFERENCES input_text_confirmation_cards(user_id, id),
    FOREIGN KEY (user_id, program_workout_id) REFERENCES program_workouts(user_id, id)
);

CREATE TABLE IF NOT EXISTS workout_session_warmups (
    id               UUID PRIMARY KEY,
    user_id          UUID NOT NULL,
    session_id       UUID NOT NULL,
    position         INT NOT NULL,
    name             TEXT NOT NULL,
    reps             INT,
    duration_seconds INT,
    notes            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (user_id, session_id) REFERENCES workout_sessions(user_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS workout_session_cooldowns (
    id               UUID PRIMARY KEY,
    user_id          UUID NOT NULL,
    session_id       UUID NOT NULL,
    position         INT NOT NULL,
    name             TEXT NOT NULL,
    reps             INT,
    duration_seconds INT,
    notes            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (user_id, session_id) REFERENCES workout_sessions(user_id, id) ON DELETE CASCADE
);

-- An exercise in a session: always one of the person's own exercises, and the name as typed.
CREATE TABLE IF NOT EXISTS workout_session_exercises (
    id                       UUID PRIMARY KEY,
    user_id                  UUID NOT NULL,
    session_id               UUID NOT NULL,
    position                 INT NOT NULL,
    user_exercise_id         UUID NOT NULL,
    name                     TEXT NOT NULL,
    notes                    TEXT,
    warmup_notes             TEXT,
    tags                     TEXT[],
    modality                 TEXT,
    movement_pattern         TEXT[],
    form_cues                TEXT[],
    target_muscle_groups     TEXT[],
    rep_tempo                TEXT,
    goal_weight_kg           NUMERIC,
    goal_sets                INT,
    goal_rep_min             INT,
    goal_rep_max             INT,
    goal_rest_min            INT,
    goal_rest_seconds        INT,
    goal_distance_meters     NUMERIC,
    goal_target_duration_sec INT,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, id),
    FOREIGN KEY (user_id, session_id) REFERENCES workout_sessions(user_id, id) ON DELETE CASCADE,
    FOREIGN KEY (user_id, user_exercise_id) REFERENCES user_exercises(user_id, id)
);

-- Warm-up and working sets in one table. Drop sets, myo-reps and the like stay as detail on their
-- set (failure_technique).
CREATE TABLE IF NOT EXISTS workout_session_sets (
    id                 UUID PRIMARY KEY,
    user_id            UUID NOT NULL,
    exercise_id        UUID NOT NULL,
    position           INT NOT NULL,
    kind               TEXT NOT NULL CHECK (kind IN ('warmup', 'working')),
    weight_kg          NUMERIC,
    reps_full          INT,
    reps_partial       INT,
    left_reps_full     INT,
    left_reps_partial  INT,
    right_reps_full    INT,
    right_reps_partial INT,
    rpe                NUMERIC,
    rep_quality        TEXT,
    rest_minutes       NUMERIC,
    rest_seconds       INT,
    duration_seconds   INT,
    distance_meters    NUMERIC,
    heart_rate_bpm     INT,
    notes              TEXT,
    failure_technique  JSONB,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (user_id, exercise_id) REFERENCES workout_session_exercises(user_id, id) ON DELETE CASCADE
);

-- Indexes: owner first --------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_input_text_user                ON input_text (user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_input_text_checksum            ON input_text (user_id, checksum);
CREATE INDEX IF NOT EXISTS idx_cards_input                    ON input_text_confirmation_cards (user_id, input_id);
CREATE INDEX IF NOT EXISTS idx_ai_call_logs_user_month        ON ai_call_logs (user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_call_logs_input             ON ai_call_logs (user_id, input_id);
CREATE INDEX IF NOT EXISTS idx_programs_user                  ON programs (user_id);
CREATE INDEX IF NOT EXISTS idx_program_workouts_program       ON program_workouts (user_id, program_id);
CREATE INDEX IF NOT EXISTS idx_program_workout_exercises      ON program_workout_exercises (user_id, workout_id);
CREATE INDEX IF NOT EXISTS idx_workout_sessions_user_date     ON workout_sessions (user_id, date);
CREATE INDEX IF NOT EXISTS idx_workout_sessions_workout       ON workout_sessions (user_id, program_workout_id);
CREATE INDEX IF NOT EXISTS idx_workout_session_warmups        ON workout_session_warmups (user_id, session_id);
CREATE INDEX IF NOT EXISTS idx_workout_session_cooldowns      ON workout_session_cooldowns (user_id, session_id);
CREATE INDEX IF NOT EXISTS idx_workout_session_exercises      ON workout_session_exercises (user_id, session_id);
CREATE INDEX IF NOT EXISTS idx_workout_session_exercises_name ON workout_session_exercises (user_id, user_exercise_id);
CREATE INDEX IF NOT EXISTS idx_workout_session_sets           ON workout_session_sets (user_id, exercise_id);

-- Row-level security on, no policies (see the top of this file) ---------------
ALTER TABLE users                         ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles                      ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercises                     ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_exercises                ENABLE ROW LEVEL SECURITY;
ALTER TABLE input_text                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE input_text_confirmation_cards ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_call_logs                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE programs                      ENABLE ROW LEVEL SECURITY;
ALTER TABLE program_workouts              ENABLE ROW LEVEL SECURITY;
ALTER TABLE program_workout_exercises     ENABLE ROW LEVEL SECURITY;
ALTER TABLE workout_sessions              ENABLE ROW LEVEL SECURITY;
ALTER TABLE workout_session_warmups       ENABLE ROW LEVEL SECURITY;
ALTER TABLE workout_session_cooldowns     ENABLE ROW LEVEL SECURITY;
ALTER TABLE workout_session_exercises     ENABLE ROW LEVEL SECURITY;
ALTER TABLE workout_session_sets          ENABLE ROW LEVEL SECURITY;
