-- Columns the exercise library replaced (0002), dropped once the code that stopped using them is
-- live: run it after that deploy, never before, since the code before it still reads them.

-- Replaced by the library's muscles and movement patterns; nothing reads them.
ALTER TABLE exercises DROP COLUMN movement, DROP COLUMN muscles;

-- Classifications the AI stopped filling, empty in every row; the library's muscles and movement
-- patterns replace them.
ALTER TABLE workout_session_exercises
    DROP COLUMN tags, DROP COLUMN modality, DROP COLUMN movement_pattern,
    DROP COLUMN target_muscle_groups, DROP COLUMN rep_tempo;
