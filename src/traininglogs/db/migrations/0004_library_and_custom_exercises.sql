-- F1, the foundation (exercise-library-plan.md, Release A): every exercise in a session or a plan
-- points at a library exercise or one of the person's custom exercises, exactly one. The tables
-- and columns take their approved names. Every existing row points at its old user_exercises row,
-- which becomes custom_exercise_id, so the checks hold before M1 repoints rows to the library.
-- The renames break the code deployed before F1, so this runs at the F1 deploy.

ALTER TABLE exercises RENAME TO library_exercises;
ALTER INDEX exercises_pkey RENAME TO library_exercises_pkey;
ALTER INDEX exercises_name_key RENAME TO library_exercises_name_key;
ALTER INDEX exercises_free_exercise_db_id_key RENAME TO library_exercises_free_exercise_db_id_key;
ALTER TABLE library_exercises RENAME CONSTRAINT exercises_free_exercise_db_id_fkey
    TO library_exercises_free_exercise_db_id_fkey;

-- Saving never creates one: a person makes a custom exercise when the library has nothing that
-- fits. Linked to a library exercise, it counts as that one.
ALTER TABLE user_exercises RENAME TO custom_exercises;
ALTER TABLE custom_exercises RENAME COLUMN exercise_id TO linked_library_exercise_id;
ALTER INDEX user_exercises_pkey RENAME TO custom_exercises_pkey;
ALTER INDEX user_exercises_user_id_id_key RENAME TO custom_exercises_user_id_id_key;
ALTER INDEX user_exercises_user_id_name_key_key RENAME TO custom_exercises_user_id_name_key_key;
ALTER TABLE custom_exercises RENAME CONSTRAINT user_exercises_user_id_fkey
    TO custom_exercises_user_id_fkey;
ALTER TABLE custom_exercises RENAME CONSTRAINT user_exercises_exercise_id_fkey
    TO custom_exercises_linked_library_exercise_id_fkey;

ALTER TABLE workout_session_exercises RENAME COLUMN user_exercise_id TO custom_exercise_id;
ALTER TABLE workout_session_exercises ALTER COLUMN custom_exercise_id DROP NOT NULL;
ALTER TABLE workout_session_exercises RENAME CONSTRAINT
    workout_session_exercises_user_id_user_exercise_id_fkey
    TO workout_session_exercises_user_id_custom_exercise_id_fkey;
ALTER TABLE workout_session_exercises
    ADD COLUMN library_exercise_id UUID REFERENCES library_exercises(id);
ALTER TABLE workout_session_exercises ADD CONSTRAINT workout_session_exercises_one_exercise
    CHECK (num_nonnulls(library_exercise_id, custom_exercise_id) = 1);
ALTER INDEX idx_workout_session_exercises_name RENAME TO idx_workout_session_exercises_custom;
CREATE INDEX idx_workout_session_exercises_library
    ON workout_session_exercises (user_id, library_exercise_id);

-- exercise_id pointed at the session exercise, not an exercise.
ALTER TABLE workout_session_sets RENAME COLUMN exercise_id TO session_exercise_id;
ALTER TABLE workout_session_sets RENAME CONSTRAINT workout_session_sets_user_id_exercise_id_fkey
    TO workout_session_sets_user_id_session_exercise_id_fkey;

ALTER TABLE program_workout_exercises RENAME COLUMN user_exercise_id TO custom_exercise_id;
ALTER TABLE program_workout_exercises ALTER COLUMN custom_exercise_id DROP NOT NULL;
ALTER TABLE program_workout_exercises RENAME CONSTRAINT
    program_workout_exercises_user_id_user_exercise_id_fkey
    TO program_workout_exercises_user_id_custom_exercise_id_fkey;
ALTER TABLE program_workout_exercises
    ADD COLUMN library_exercise_id UUID REFERENCES library_exercises(id);
ALTER TABLE program_workout_exercises ADD CONSTRAINT program_workout_exercises_one_exercise
    CHECK (num_nonnulls(library_exercise_id, custom_exercise_id) = 1);
ALTER TABLE program_workout_exercises ADD UNIQUE (user_id, id);

-- Exercises that can take a plan exercise's place, one row each, in order. Replaces the
-- alternatives names, which M1 moves here; 0005 drops that column.
CREATE TABLE program_workout_exercise_alternatives (
    id                          UUID PRIMARY KEY,
    user_id                     UUID NOT NULL,
    program_workout_exercise_id UUID NOT NULL,
    position                    INT NOT NULL CHECK (position > 0),
    library_exercise_id         UUID REFERENCES library_exercises(id),
    custom_exercise_id          UUID,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, id),
    CONSTRAINT program_workout_exercise_alternatives_plan_exercise_fkey
        FOREIGN KEY (user_id, program_workout_exercise_id)
        REFERENCES program_workout_exercises(user_id, id) ON DELETE CASCADE,
    CONSTRAINT program_workout_exercise_alternatives_custom_exercise_fkey
        FOREIGN KEY (user_id, custom_exercise_id) REFERENCES custom_exercises(user_id, id),
    CONSTRAINT program_workout_exercise_alternatives_one_exercise
        CHECK (num_nonnulls(library_exercise_id, custom_exercise_id) = 1)
);
CREATE INDEX idx_program_workout_exercise_alternatives
    ON program_workout_exercise_alternatives (user_id, program_workout_exercise_id);
ALTER TABLE program_workout_exercise_alternatives ENABLE ROW LEVEL SECURITY;
