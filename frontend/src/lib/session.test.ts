import { describe, expect, it } from 'vitest'
import {
  addWarmupSet,
  counts,
  switchExercise,
  setMovements,
  recordCardio,
  startFromPast,
  wantsWarmupNudge,
  saveSet,
  startFromWorkout,
  toggleDone,
  toRequest,
  type LastExercise,
  addRamp,
  needsEffort,
  rampSets,
  setLastEffort,
  setValue,
  addSet,
  startBlank,
  addExercise,
} from './session'
import type { Workout } from './types'

const workout: Workout = {
  id: 'w1',
  position: 1,
  name: 'Bench',
  last_done: null, warmup: [], cooldown: [],
  exercises: [
    { name: 'Squat', warmup_sets: 1, working_sets: 3, target_reps: 2, amrap: false, alternatives: [] },
    { name: 'Chinups', warmup_sets: 0, working_sets: 1, target_reps: null, amrap: true, alternatives: [] },
    { name: 'Deadlift', warmup_sets: 0, working_sets: 1, target_reps: 5, amrap: false, alternatives: [] },
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

    const finished = new Date(2026, 9, 4, 10, 52)
    const req = toRequest(s, finished)
    expect(req.duration_minutes).toBe(52)
    expect([req.started_at, req.ended_at]).toEqual([now.toISOString(), finished.toISOString()])
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

describe('the set drawer', () => {
  it('keeps last time as a suggestion when only effort or a note changes', () => {
    let s = startFromWorkout(workout, '1 · Bench', 'p1', lasts, now)
    const set = s.exercises[0].sets[1]
    s = saveSet(s, set.key, { kind: 'working', weight: set.weight, reps: set.reps, rpe: 8.5, note: 'grind' })
    expect(s.exercises[0].sets[1]).toMatchObject({ ghost: true, rpe: 8.5, note: 'grind' })
  })
})

describe('alternatives', () => {
  const line = { name: 'Shoulder Press', warmup_sets: 1, working_sets: 2, target_reps: 5, amrap: false, alternatives: ['Bench press'] }
  const w = { ...workout, exercises: [line] }
  const lasts: LastExercise[] = [
    { name: 'Shoulder Press', date: '2026-10-02', notes: 'easy', warmup_sets: [{ weight_kg: 30, reps: 5, notes: null }], sets: [{ weight_kg: 60, reps: 5, notes: null }] },
    { name: 'Bench press', date: '2026-09-30', notes: 'still hard', warmup_sets: [{ weight_kg: 40, reps: 5, notes: null }], sets: [{ weight_kg: 90, reps: 2, notes: null }, { weight_kg: 87.5, reps: 2, notes: null }] },
  ]

  it('starts with the first exercise and keeps every choice', () => {
    const s = startFromWorkout(w, 't', 'p1', lasts, now)
    expect(s.exercises[0].name).toBe('Shoulder Press')
    expect(s.exercises[0].choices).toEqual(['Shoulder Press', 'Bench press'])
    expect(s.exercises[0].sets.map((x) => x.weight)).toEqual(['30', '60', '60'])
  })

  it('switching refills untouched sets from the new exercise and keeps ticked ones', () => {
    let s = startFromWorkout(w, 't', 'p1', lasts, now)
    const ex = s.exercises[0]
    s = toggleDone(s, ex.sets[0].key)
    s = switchExercise(s, ex.key, 'Bench press')
    const after = s.exercises[0]
    expect(after.name).toBe('Bench press')
    expect(after.lastNote).toBe('still hard')
    expect(after.sets.map((x) => [x.weight, x.done, x.last])).toEqual([
      ['30', true, '40 × 5'],
      ['90', false, '90 × 2'],
      ['87.5', false, '87.5 × 2'],
    ])
  })

})

describe('warm-up and cool-down', () => {
  it('come from the workout and only ticked ones are sent', () => {
    const w = {
      ...workout,
      warmup: [{ name: 'Easy cardio', reps: null, duration_seconds: 180 }, { name: 'Arm circles', reps: 10, duration_seconds: null }],
      cooldown: [{ name: 'Stretch', reps: null, duration_seconds: 300 }],
    }
    let s = startFromWorkout(w, 't', 'p1', [], now)
    expect(s.warmup?.map((m) => [m.name, m.amount, m.done])).toEqual([['Easy cardio', '3 min', false], ['Arm circles', '10', false]])
    s = setMovements(s, 'warmup', s.warmup!.map((m, i) => (i === 0 ? { ...m, done: true } : m)))
    s = toggleDone(s, s.exercises[0].sets[0].key)
    const req = toRequest(s, now)
    expect(req.warmup).toEqual([{ name: 'Easy cardio', reps: null, duration_seconds: 180, notes: null }])
    expect(req.cooldown).toEqual([])
  })
})

describe('a movement amount the rule cannot read', () => {
  it('is kept as the note', () => {
    let s = startFromWorkout({ ...workout, warmup: [{ name: 'Leg swings', reps: null, duration_seconds: null }] }, 't', 'p1', [], now)
    s = setMovements(s, 'warmup', s.warmup!.map((m) => ({ ...m, amount: 'each side 10', done: true })))
    expect(toRequest(s, now).warmup).toEqual([{ name: 'Leg swings', reps: null, duration_seconds: null, notes: 'each side 10' }])
  })
})

describe('warm-up nudge', () => {
  it('records the minutes since the timer started, within 1 and 5', () => {
    const s = { ...startFromWorkout(workout, 't', 'p1', [], now), cardioStartedAt: new Date(2026, 9, 4, 10, 0).toISOString() }
    expect(wantsWarmupNudge(s)).toBe(true)
    const after = recordCardio(s, new Date(2026, 9, 4, 10, 3, 10))
    expect(after.warmup?.map((m) => [m.name, m.amount, m.done])).toEqual([['Easy cardio', '3 min', true]])
    expect(wantsWarmupNudge(after)).toBe(false)
    expect(recordCardio(s, new Date(2026, 9, 4, 10, 30)).warmup?.[0].amount).toBe('5 min')
  })

  it('ticks an Easy cardio row already there instead of adding another', () => {
    const s = startFromWorkout({ ...workout, warmup: [{ name: 'Easy cardio', reps: null, duration_seconds: 300 }] }, 't', 'p1', [], now)
    expect(recordCardio(s, now).warmup?.map((m) => [m.name, m.done])).toEqual([['Easy cardio', true]])
  })
})

describe('doing a past session again', () => {
  it('copies its exercises and set counts, with its values in grey', () => {
    const past = {
      session_id: 's1', date: '2026-10-02', program: null, focus: null, duration_minutes: 40, notes: null,
      program_name: null, workout_position: null, workout_name: null, source_kind: 'manual' as const,
      exercises: [{
        number: 1, name: 'Squat', notes: 'better depth',
        warmup_sets: [{ number: 1, weight_kg: 80, rep_count: 3, notes: null }],
        sets: [{ number: 1, weight_kg: 125, reps_full: 2, reps_partial: null, left_reps_full: null, right_reps_full: null, rpe: 9, notes: null }],
      }],
    }
    const s = startFromPast(past, now)
    expect(s.title).toBe('Squat')
    expect(s.workoutId).toBeNull()
    expect(s.exercises[0].lastNote).toBe('better depth')
    expect(s.exercises[0].sets.map((x) => [x.kind, x.weight, x.reps, x.ghost, x.last])).toEqual([
      ['warmup', '80', '3', true, '80 × 3'],
      ['working', '125', '2', true, '125 × 2'],
    ])
  })
})

describe('warm-up ramp', () => {
  it('climbs in weight as reps drop, rounded to 2.5 kg', () => {
    // 50%, 75% and 95%: spread evenly over 50 to 95, in steps of 5.
    expect(rampSets(120, 3)).toEqual([{ kg: 60, reps: 5 }, { kg: 90, reps: 3 }, { kg: 115, reps: 1 }])
    expect(rampSets(100, 10).map((r) => r.kg)).toEqual([50, 55, 60, 65, 70, 75, 80, 85, 90, 95])
    expect(rampSets(120, 11)).toEqual([])
    expect(rampSets(120, 0)).toEqual([])
  })

  it('adds grey warm-ups before the working sets and keeps the ones already there', () => {
    const s = startFromWorkout(workout, 'Bench', 'p1', lasts, now)
    const before = s.exercises[0].sets
    const after = addRamp(s, s.exercises[0].key, rampSets(120, 2)).exercises[0].sets
    expect(after.length).toBe(before.length + 2)
    const warm = before.filter((x) => x.kind === 'warmup').length
    expect(after.slice(0, warm)).toEqual(before.slice(0, warm))
    expect(after.slice(warm, warm + 2).map((x) => [x.kind, x.weight, x.reps, x.ghost])).toEqual([
      ['warmup', '60', '5', true], ['warmup', '115', '1', true],
    ])
  })
})

describe('effort nudge', () => {
  it('asks once an exercise is done with no effort, and stops after an answer or Skip', () => {
    let s = startFromWorkout(workout, 'Bench', 'p1', lasts, now)
    const ex = s.exercises[0]
    expect(needsEffort(ex)).toBe(false)
    for (const set of ex.sets) s = toggleDone(s, set.key)
    expect(needsEffort(s.exercises[0])).toBe(true)
    const answered = setLastEffort(s, ex.key, 8.5)
    expect(answered.exercises[0].sets.filter((x) => x.kind === 'working').at(-1)?.rpe).toBe(8.5)
    expect(needsEffort(answered.exercises[0])).toBe(false)
    expect(needsEffort({ ...s.exercises[0], effortSkipped: true })).toBe(false)
  })
})

describe('cascade fill', () => {
  it("a typed weight shows in grey in the later sets of the same kind nobody has touched", () => {
    const s = startFromWorkout(workout, '1 · Bench', 'p1', lasts, now)
    const squat = s.exercises[0]
    const after = setValue(s, squat.sets[1].key, 'weight', '130').exercises[0].sets
    expect(after.map((x) => [x.kind, x.weight, x.reps, x.ghost])).toEqual([
      ['warmup', '80', '', true], // a warm-up: another kind, left alone
      ['working', '130', '2', false], // typed
      ['working', '130', '2', true], // last time's 125 replaced, still grey
      ['working', '130', '2', true],
    ])
  })

  it("leaves ticked and typed-into sets alone, and doesn't spread a cleared box", () => {
    let s = startBlank(now)
    s = addExercise(s).session
    const ex = s.exercises[0].key
    s = addSet(s, ex).session
    s = addSet(s, ex).session
    const [a, b, c] = s.exercises[0].sets
    s = setValue(s, b.key, 'reps', '8') // typed into; the 8 also shows in grey in the set below
    s = toggleDone(s, c.key) // ticked, taking the grey 8
    s = setValue(s, a.key, 'weight', '60')
    expect(s.exercises[0].sets.map((x) => [x.weight, x.reps, x.done])).toEqual([['60', '', false], ['', '8', false], ['', '8', true]])
    s = setValue(s, a.key, 'weight', '')
    expect(s.exercises[0].sets.map((x) => x.weight)).toEqual(['', '', ''])
  })
})
