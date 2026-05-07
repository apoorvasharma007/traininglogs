-- Migration: data model flexibility + activity support
-- Additive only — no column drops or renames.
-- Apply once against any DB running schema.sql at v1.0.0.

ALTER TABLE working_sets
    ADD COLUMN IF NOT EXISTS set_type        TEXT NOT NULL DEFAULT 'strength',
    ADD COLUMN IF NOT EXISTS duration_seconds INT,
    ADD COLUMN IF NOT EXISTS distance_meters  NUMERIC,
    ADD COLUMN IF NOT EXISTS heart_rate_bpm   INT,
    ADD COLUMN IF NOT EXISTS left_reps_full   INT,
    ADD COLUMN IF NOT EXISTS left_reps_partial INT,
    ADD COLUMN IF NOT EXISTS right_reps_full  INT,
    ADD COLUMN IF NOT EXISTS right_reps_partial INT,
    ADD COLUMN IF NOT EXISTS rest_seconds     INT;

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS weight_unit TEXT NOT NULL DEFAULT 'kg';

ALTER TABLE exercises
    ADD COLUMN IF NOT EXISTS exercise_type           TEXT NOT NULL DEFAULT 'strength',
    ADD COLUMN IF NOT EXISTS goal_rest_seconds        INT,
    ADD COLUMN IF NOT EXISTS goal_distance_meters     NUMERIC,
    ADD COLUMN IF NOT EXISTS goal_target_duration_sec INT;
