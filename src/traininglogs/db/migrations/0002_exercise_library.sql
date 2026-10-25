-- The exercise library (exercise-library-plan.md, steps 3 and 4): the approved lists, the
-- free-exercise-db table, and the library's columns on exercises and user_exercises. It only adds,
-- so it runs before the code that uses it deploys; 0003 drops the columns these replace, after.
-- scripts/load_exercise_library.py fills the tables afterwards.

-- The approved lists (exercise-library-plan.md, section 2). The database refuses a value that
-- isn't on them, whoever writes it. To change a list, a new file drops the check and adds it again;
-- the add fails if a stored value is no longer on the list.
CREATE DOMAIN muscle_list AS TEXT[]
    CONSTRAINT muscle_list_check CHECK (VALUE <@ ARRAY[
        'Upper Chest', 'Mid/Lower Chest', 'Front Delts', 'Side Delts', 'Rear Delts',
        'Rotator Cuff', 'Serratus', 'Lats', 'Upper Traps', 'Mid Traps', 'Lower Traps', 'Rhomboids',
        'Spinal Erectors', 'Quadratus Lumborum', 'Biceps', 'Brachialis', 'Triceps Long Head',
        'Triceps Lateral/Medial Heads', 'Brachioradialis', 'Forearm Flexors', 'Forearm Extensors',
        'Abs', 'Obliques', 'Transverse Abdominis', 'Glute Max', 'Glute Med', 'Abductors', 'Adductors',
        'Hip Flexors', 'Rectus Femoris', 'Vastus Muscles', 'Hamstrings', 'Gastrocnemius', 'Soleus',
        'Tibialis', 'Neck Flexors', 'Neck Extensors'
    ]::text[]);
CREATE DOMAIN joint_action_list AS TEXT[]
    CONSTRAINT joint_action_list_check CHECK (VALUE <@ ARRAY[
        'shoulder flexion', 'shoulder extension', 'shoulder abduction', 'shoulder adduction',
        'shoulder horizontal abduction', 'shoulder horizontal adduction',
        'shoulder internal rotation', 'shoulder external rotation', 'shoulder blade elevation',
        'shoulder blade depression', 'shoulder blade protraction', 'shoulder blade retraction',
        'shoulder blade upward rotation', 'shoulder blade downward rotation', 'elbow flexion',
        'elbow extension', 'forearm pronation', 'forearm supination', 'wrist flexion',
        'wrist extension', 'wrist radial deviation', 'wrist ulnar deviation', 'trunk flexion',
        'trunk extension', 'trunk lateral flexion', 'trunk rotation', 'neck flexion',
        'neck extension', 'neck lateral flexion', 'neck rotation', 'hip flexion', 'hip extension',
        'hip abduction', 'hip adduction', 'hip internal rotation', 'hip external rotation',
        'knee flexion', 'knee extension', 'knee internal rotation', 'knee external rotation',
        'ankle dorsiflexion', 'ankle plantarflexion', 'foot inversion', 'foot eversion'
    ]::text[]);
CREATE DOMAIN movement_pattern_list AS TEXT[]
    CONSTRAINT movement_pattern_list_check CHECK (VALUE <@ ARRAY[
        'Squat', 'Hinge', 'Lunge', 'Horizontal Push', 'Vertical Push', 'Horizontal Pull',
        'Vertical Pull', 'Carry', 'Jump', 'Throw', 'Rotation', 'Anti-Rotation', 'Anti-Extension',
        'Anti-Flexion', 'Anti-Lateral Flexion'
    ]::text[]);
CREATE DOMAIN measure_list AS TEXT[]
    CONSTRAINT measure_list_check CHECK (VALUE <@ ARRAY[
        'weight', 'reps', 'time', 'distance'
    ]::text[]);
CREATE DOMAIN equipment_name AS TEXT
    CONSTRAINT equipment_name_check CHECK (VALUE IN (
        'barbell', 'ez bar', 'trap bar', 'dumbbell', 'kettlebell', 'cable', 'machine',
        'smith machine', 'band', 'medicine ball', 'sled', 'box', 'jump rope', 'bodyweight',
        'other'
    ));

-- free-exercise-db's exercises, unchanged, loaded by scripts/load_exercise_library.py from the
-- copy in scripts/data/. Nobody edits it by hand. Shared reference data, so no owner.
CREATE TABLE free_exercise_db (
    id                TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    force             TEXT,
    level             TEXT,
    mechanic          TEXT,
    equipment         TEXT,
    category          TEXT,
    primary_muscles   TEXT[] NOT NULL,
    secondary_muscles TEXT[] NOT NULL,
    instructions      TEXT[] NOT NULL,
    images            TEXT[] NOT NULL
);
ALTER TABLE free_exercise_db ENABLE ROW LEVEL SECURITY;

-- The shared, curated library, loaded by scripts/load_exercise_library.py from
-- db/exercise_library.yaml. People's own exercises never change it.
ALTER TABLE exercises ADD COLUMN measures            measure_list          NOT NULL DEFAULT '{}';
-- Moves two or more joints (compound) or one (isolation); NULL when not set.
ALTER TABLE exercises ADD COLUMN compound            BOOLEAN;
ALTER TABLE exercises ADD COLUMN primary_muscles     muscle_list           NOT NULL DEFAULT '{}';
ALTER TABLE exercises ADD COLUMN secondary_muscles   muscle_list           NOT NULL DEFAULT '{}';
ALTER TABLE exercises ADD COLUMN joint_actions       joint_action_list     NOT NULL DEFAULT '{}';
ALTER TABLE exercises ADD COLUMN movement_patterns   movement_pattern_list NOT NULL DEFAULT '{}';
-- One of theirs links to one of ours at most.
ALTER TABLE exercises ADD COLUMN free_exercise_db_id TEXT UNIQUE REFERENCES free_exercise_db(id);
-- The equipment list moves to its domain, shared with user_exercises.
ALTER TABLE exercises DROP CONSTRAINT exercises_equipment_check;
ALTER TABLE exercises ALTER COLUMN equipment TYPE equipment_name;

-- What a person's own exercise records, with the library's column names. A custom exercise has a
-- primary muscle; a name that has none and no link is unrecognized. A linked one keeps these, so
-- unlinking restores them.
ALTER TABLE user_exercises ADD COLUMN equipment         equipment_name;
-- What "other" equipment is, in the person's words.
ALTER TABLE user_exercises ADD COLUMN equipment_other   TEXT;
ALTER TABLE user_exercises ADD COLUMN measures          measure_list          NOT NULL DEFAULT '{}';
ALTER TABLE user_exercises ADD COLUMN compound          BOOLEAN;
ALTER TABLE user_exercises ADD COLUMN primary_muscles   muscle_list           NOT NULL DEFAULT '{}';
ALTER TABLE user_exercises ADD COLUMN secondary_muscles muscle_list           NOT NULL DEFAULT '{}';
ALTER TABLE user_exercises ADD COLUMN joint_actions     joint_action_list     NOT NULL DEFAULT '{}';
ALTER TABLE user_exercises ADD COLUMN movement_patterns movement_pattern_list NOT NULL DEFAULT '{}';
