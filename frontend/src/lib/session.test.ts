import { describe, expect, it } from 'vitest'
import {
  addWarmupSet,
  counts,
  planFromSession,
  saveSet,
  startFromWorkout,
  toggleDone,
  toRequest,
  type LastExercise,
} from './session'
import type { Workout } from './types'

const workout: Workout = {
  id: 'w1',
  position: 1,
  name: 'Bench',
  last_done: null,
  exercises: [
    { name: 'Squat', warmup_sets: 1, working_sets: 3, target_reps: 2, amrap: false },
    { name: 'Chinups', warmup_sets: 0, working_sets: 1, target_reps: null, amrap: true },
    { name: 'Deadlift', warmup_sets: 0, working_sets: 1, target_reps: 5, amrap: false },
  ],
}
const lasts: LastExercise[] = [
  {
    name: 'squat', date: '2026-10-02', notes: 'better depth',
    warmup_sets: [{ weight_kg: 80, reps: null, notes: null }],
    sets: [{ weight_kg: 120, reps: 2, notes: null }, { weight_kg: 125, reps: 2, notes: null }],
  },
  { name: 'Chinups', date: '2026-09-28', notes: null, warmup_sets: [], sets: [{ weight_kg: 0, reps: 19, notes: null }] },
]
const now = new Date(2026, 9, 4, 10, 0)

describe('starting from a workout', () => {
  const s = startFromWorkout(workout, '1 · Bench', 'p1', lasts, now)

  it('takes the plan and fills it from last time, in grey', () => {
    expect(s.date).toBe('2026-10-04')
    const squat = s.exercises[0]
    expect(squat.lastNote).toBe('better depth')
    expect(squat.sets.map((x) => [x.kind, x.weight, x.reps, x.last, x.ghost])).toEqual([
      ['warmup', '80', '', '80 × ?', true],
      ['working', '120', '2', '120 × 2', true],
      ['working', '125', '2', '125 × 2', true],
      // A third set the plan has and last time didn't: same as the last one, no "last" value.
      ['working', '125', '2', null, true],
    ])
  })

  it('reads bodyweight and as-many-as-you-can sets', () => {
    expect(s.exercises[1].sets.map((x) => [x.weight, x.reps, x.last])).toEqual([['0', '19', 'BW × 19']])
  })

  it('uses the target reps when the exercise was never logged', () => {
    expect(s.exercises[2].sets.map((x) => [x.weight, x.reps, x.ghost, x.last])).toEqual([['', '5', true, null]])
  })
})

describe('Finish', () => {
  it('sends only ticked sets and leaves out exercises with none', () => {
    let s = startFromWorkout(workout, '1 · Bench', 'p1', lasts, now)
    const squat = s.exercises[0]
    s = toggleDone(s, squat.sets[0].key)
    s = saveSet(s, squat.sets[1].key, { kind: 'working', weight: '122.5', reps: '2', rpe: 8, note: 'fast' })
    s = toggleDone(s, squat.sets[1].key)
    expect(counts(s)).toEqual({ done: 2, total: 6 })

    const req = toRequest(s, new Date(2026, 9, 4, 10, 52))
    expect(req.duration_minutes).toBe(52)
    expect(req.program_workout_id).toBe('w1')
    expect(req.exercises).toEqual([
      {
        name: 'Squat',
        notes: null,
        warmup_sets: [{ weight_kg: 80, reps: null, notes: null }],
        sets: [{ weight_kg: 122.5, reps: 2, rpe: 8, notes: 'fast' }],
      },
    ])
  })

  it('offers a new plan only when the sets differ from it', () => {
    const s = startFromWorkout(workout, '1 · Bench', 'p1', lasts, now)
    expect(planFromSession(s, workout.exercises)).toBeNull()
    const more = addWarmupSet(s, s.exercises[2].key).session
    expect(planFromSession(more, workout.exercises)?.[2]).toEqual(
      { name: 'Deadlift', warmup_sets: 1, working_sets: 1, target_reps: 5, amrap: false },
    )
  })
})

describe('adding a warmup set', () => {
  it('starts at half the first working set, rounded to 2.5 kg, before the working sets', () => {
    const s = startFromWorkout({ ...workout, exercises: [{ ...workout.exercises[0], warmup_sets: 0 }] }, 't', 'p1', lasts, now)
    const { session } = addWarmupSet(s, s.exercises[0].key)
    expect(session.exercises[0].sets.map((x) => [x.kind, x.weight])).toEqual([
      ['warmup', '60'], ['working', '120'], ['working', '125'], ['working', '125'],
    ])
  })
})
