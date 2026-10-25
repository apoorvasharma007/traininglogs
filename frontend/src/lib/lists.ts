// The exercise library's fixed lists, as `schema.sql` checks them (exercise-library-plan.md,
// section 2). Adding to a list changes `schema.sql` and this file together.
// Muscle groups, their muscles and joints run head to toe; everything else is alphabetical.

/** Muscle groups and their muscles. */
export const MUSCLE_GROUPS: [string, string[]][] = [
  ['Neck', ['Neck Flexors', 'Neck Extensors']],
  ['Shoulders', ['Front Delts', 'Side Delts', 'Rear Delts', 'Rotator Cuff']],
  ['Chest', ['Upper Chest', 'Mid/Lower Chest']],
  ['Upper Back', ['Upper Traps', 'Mid Traps', 'Rhomboids', 'Lower Traps']],
  ['Lats', ['Lats']],
  ['Serratus', ['Serratus']],
  ['Biceps', ['Biceps', 'Brachialis']],
  ['Triceps', ['Triceps Long Head', 'Triceps Lateral/Medial Heads']],
  ['Forearms', ['Brachioradialis', 'Forearm Flexors', 'Forearm Extensors']],
  ['Core', ['Abs', 'Obliques', 'Transverse Abdominis']],
  ['Lower Back', ['Spinal Erectors', 'Quadratus Lumborum']],
  ['Glutes', ['Glute Max', 'Glute Med']],
  ['Hips', ['Hip Flexors', 'Abductors', 'Adductors']],
  ['Quads', ['Rectus Femoris', 'Vastus Muscles']],
  ['Hamstrings', ['Hamstrings']],
  ['Calves', ['Gastrocnemius', 'Soleus']],
  ['Shins', ['Tibialis']],
]

/** Joints and their joint movements, stored as "<joint> <movement>": "shoulder blade elevation". */
export const JOINTS: [string, string[]][] = [
  ['Neck', ['extension', 'flexion', 'lateral flexion', 'rotation']],
  ['Shoulder Blade', ['depression', 'downward rotation', 'elevation', 'protraction', 'retraction', 'upward rotation']],
  ['Shoulder', ['abduction', 'adduction', 'extension', 'external rotation', 'flexion', 'horizontal abduction', 'horizontal adduction', 'internal rotation']],
  ['Elbow', ['extension', 'flexion']],
  ['Forearm', ['pronation', 'supination']],
  ['Wrist', ['extension', 'flexion', 'radial deviation', 'ulnar deviation']],
  ['Trunk', ['extension', 'flexion', 'lateral flexion', 'rotation']],
  ['Hip', ['abduction', 'adduction', 'extension', 'external rotation', 'flexion', 'internal rotation']],
  ['Knee', ['extension', 'external rotation', 'flexion', 'internal rotation']],
  ['Ankle', ['dorsiflexion', 'plantarflexion']],
  ['Foot', ['eversion', 'inversion']],
]

export const MOVEMENT_PATTERNS = [
  'Anti-Extension', 'Anti-Flexion', 'Anti-Lateral Flexion', 'Anti-Rotation', 'Carry', 'Hinge',
  'Horizontal Pull', 'Horizontal Push', 'Jump', 'Lunge', 'Rotation', 'Squat', 'Throw',
  'Vertical Pull', 'Vertical Push',
]

export const EQUIPMENT = [
  'band', 'barbell', 'bodyweight', 'box', 'cable', 'dumbbell', 'ez bar', 'jump rope', 'kettlebell',
  'machine', 'medicine ball', 'other', 'sled', 'smith machine', 'trap bar',
]

export type Measure = 'weight' | 'reps' | 'time' | 'distance'

/** What a set logs: the seven combinations that occur. */
export const LOGS: [string, Measure[]][] = [
  ['Distance and Time', ['distance', 'time']],
  ['Reps', ['reps']],
  ['Reps and Distance', ['reps', 'distance']],
  ['Time', ['time']],
  ['Weight and Distance', ['weight', 'distance']],
  ['Weight and Reps', ['weight', 'reps']],
  ['Weight and Time', ['weight', 'time']],
]
