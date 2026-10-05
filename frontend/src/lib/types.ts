// Shapes of the API's replies, mirroring src/traininglogs/api/schemas.py. Only the fields the
// screens read are listed.

export type SessionSummary = {
  session_id: string
  date: string
  program: string | null
  focus: string | null
  exercises: string[]
}

type WarmupSet = { number: number; weight_kg: number | null; rep_count: number | null; notes: string | null }

export type WorkingSet = {
  number: number
  weight_kg: number | null
  reps_full: number | null
  reps_partial: number | null
  left_reps_full: number | null
  right_reps_full: number | null
  rpe: number | null
  notes: string | null
}

export type SessionExercise = {
  number: number
  name: string
  notes: string | null
  sets: WorkingSet[]
  warmup_sets: WarmupSet[]
}

export type SessionDetail = {
  session_id: string
  date: string
  program: string | null
  focus: string | null
  duration_minutes: number | null
  notes: string | null
  exercises: SessionExercise[]
}

export type Measure = 'estimated_max' | 'bodyweight_reps'

export type LiftSummary = {
  name: string
  measure: Measure
  sessions: number
  latest: number | null
  best: number | null
  last_date: string | null
  trend: 'up' | 'flat' | 'down' | null
}

export type LiftsOut = { key_lifts: LiftSummary[]; other_lifts: LiftSummary[] }

export type LiftPoint = {
  session_id: string
  date: string
  value: number | null
  method: 'rpe' | null // null: no set had an RPE, so value is null and heaviest_kg stands in
  heaviest_kg: number | null
  records: string[]
  best_set: { number: number; weight_kg: number | null; reps: number | null; rpe: number | null }
}

export type LiftDetail = LiftSummary & { points: LiftPoint[] }

// The review card (agent/validation_card_data.py). Each line's `path` is what /edit addresses.
export type CardWarmupRow = {
  number: number
  weight_kg: number
  rep_count: number | null
  notes: string | null
  uncertain_fields: string[] // what the AI wasn't sure of: weight_kg, rep_count
  path: string
}

export type CardSetRow = {
  number: number
  weight_kg: number | null
  reps: string | null
  rpe: number | null
  notes: string | null
  uncertain_fields: string[] // what the AI wasn't sure of: weight_kg, reps, rpe
  path: string
}

export type CardExercise = {
  header: { number: number; name: string; failed: boolean; path: string }
  warmup_rows: CardWarmupRow[]
  working_set_rows: CardSetRow[]
  note_preview: { full_text: string } | null
  failure_reason: string | null
}

export type Card = {
  session_header: {
    date: string
    focus: string | null
    program: string | null
    duration_minutes: number | null
    uncertain_fields: string[]
    path: string
  }
  exercises: CardExercise[]
  warnings: string[]
}

export type CaptureOut = { raw_input_id: string; extraction_id: string | null; error: string | null }

export type CardEdit = { path: string; field: string; value: unknown }
export type CardOp = { op: 'add_set' | 'add_warmup_set' | 'add_exercise' | 'remove'; path: string }

export type EditReply = {
  extract: Record<string, unknown>
  card: Card
  correction: Record<string, unknown>
  created_path: string | null
}

export type PlanExercise = {
  name: string
  warmup_sets: number
  working_sets: number
  target_reps: number | null
  amrap: boolean
  alternatives: string[] // other exercises that can take this line's place
}

/** A warm-up or cool-down movement: reps, a duration, or neither. */
export type Movement = { name: string; reps: number | null; duration_seconds: number | null }

export type Workout = {
  id: string
  position: number
  name: string | null
  last_done: string | null
  exercises: PlanExercise[]
  warmup: Movement[]
  cooldown: Movement[]
}

export type Program = {
  id: string
  name: string
  deload_after_days: number
  following: boolean
  following_since: string | null
  workouts: Workout[]
  next_workout_id: string | null
  deload: { days_since: number; due: boolean; in_progress: number }
}

/** A ready-made program to copy into your own. */
export type ProgramTemplate = {
  id: string
  name: string
  days: string // "3 days a week"
  workouts: { name: string; exercises: PlanExercise[] }[]
}
