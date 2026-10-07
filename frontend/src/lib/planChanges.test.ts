import { describe, expect, it } from 'vitest'
import { applyChanges, planChanges } from './planChanges'
import {
  addExercise, addSet, addWarmupSet, changeMovement, moveExercise, recordCardio, removeExercise, removeSet, setMovements, setWarmups,
  startFromWorkout, switchExercise, toggleDone, updateExercise, type LiveSession,
} from './session'
import type { Workout } from './types'

const workout: Workout = {
  id: 'w2', position: 2, name: null, last_done: null,
  warmup: [{ name: 'Easy cardio', reps: null, duration_seconds: 300 }], cooldown: [],
  exercises: [
    { name: 'Squat', warmup_sets: 2, working_sets: 3, target_reps: 5, amrap: false, alternatives: [] },
    { name: 'Shoulder Press', warmup_sets: 0, working_sets: 3, target_reps: 5, amrap: false, alternatives: ['Bench press'] },
    { name: 'Calf raise', warmup_sets: 0, working_sets: 3, target_reps: null, amrap: true, alternatives: [] },
  ],
}
// A session that followed the plan, its planned warm-up done.
const start = (): LiveSession => {
  const s = startFromWorkout(workout, 'Workout 2', 'p1', [], new Date(2026, 9, 4))
  return changeMovement(s, 'warmup', s.warmup![0].key, { done: true })
}
const labels = (changes: ReturnType<typeof planChanges>) => changes.map((c) => [c.label, c.on])

describe('changes to save back to the program', () => {
  it('none when the session followed the plan, even with its sets unticked', () => {
    expect(planChanges(start(), workout)).toEqual([])
  })

  it('an extra set counts only once it is ticked', () => {
    const base = start()
    const added = addWarmupSet(base, base.exercises[0].key)
    expect(planChanges(added.session, workout)).toEqual([])
    const s = toggleDone(added.session, added.setKey)
    expect(labels(planChanges(s, workout))).toEqual([['Squat: 3 warm-up sets (was 2)', true]])
  })

  it('a new exercise is offered with its ticked sets, and not at all with none', () => {
    const added = addExercise(start())
    let s = updateExercise(added.session, added.exKey, { name: 'Face pulls', naming: false })
    const set = addSet(s, added.exKey)
    expect(planChanges(set.session, workout)).toEqual([])
    s = toggleDone(set.session, set.setKey)
    expect(labels(planChanges(s, workout))).toEqual([['Add Face pulls (1 set)', true]])
  })

  it('removing an exercise or deleting planned sets is offered unticked', () => {
    let s = start()
    s = removeExercise(s, s.exercises[2].key)
    s = removeSet(s, s.exercises[0].sets[4].key)
    expect(labels(planChanges(s, workout))).toEqual([
      ['Squat: 2 working sets (was 3)', false],
      ['Remove Calf raise', false],
    ])
  })

  it('a renamed exercise is one line, unticked, matched by where it came from', () => {
    const s = start()
    const renamed = updateExercise(s, s.exercises[0].key, { name: 'Sqaut' })
    expect(labels(planChanges(renamed, workout))).toEqual([['Squat → Sqaut', false]])
    const plan = applyChanges(workout, planChanges(renamed, workout), new Set(['rename-0']))
    expect(plan.exercises[0]).toMatchObject({ name: 'Sqaut', warmup_sets: 2, working_sets: 3 })
  })

  it('a different capitalisation is not a rename', () => {
    const s = start()
    expect(planChanges(updateExercise(s, s.exercises[0].key, { name: 'squat ' }), workout)).toEqual([])
  })

  it('switching to an alternative offers to make it the main exercise, unticked', () => {
    const s = start()
    const switched = switchExercise(s, s.exercises[1].key, 'Bench press')
    expect(labels(planChanges(switched, workout))).toEqual([['Make Bench press the main exercise', false]])
    const plan = applyChanges(workout, planChanges(switched, workout), new Set(['main-1']))
    expect(plan.exercises[1]).toMatchObject({ name: 'Bench press', alternatives: ['Shoulder Press'] })
  })

  it('a warm-up set template keeps the planned count; only its ticked extras add', () => {
    let s = start()
    s = setWarmups(s, s.exercises[0].key, [{ kg: 20, reps: 10 }, { kg: 40, reps: 5 }, { kg: 60, reps: 3 }])
    expect(planChanges(s, workout)).toEqual([])
    s = toggleDone(s, s.exercises[0].sets[2].key)
    expect(labels(planChanges(s, workout))).toEqual([['Squat: 3 warm-up sets (was 2)', true]])
  })

  it('a new ticked warm-up movement is offered; an unticked one is not', () => {
    let s = start()
    s = setMovements(s, 'warmup', [
      ...s.warmup!,
      { key: 'a', name: 'Leg swings', amount: '10', done: true },
      { key: 'b', name: 'Hip circles', amount: '', done: false },
    ])
    expect(labels(planChanges(s, workout))).toEqual([['Warm-up: add Leg swings (10)', true]])
  })

  it('a skipped planned movement is offered for removal, unticked', () => {
    const s = startFromWorkout(workout, 'Workout 2', 'p1', [], new Date(2026, 9, 4))
    expect(labels(planChanges(s, workout))).toEqual([['Warm-up: remove Easy cardio', false]])
    const plan = applyChanges(workout, planChanges(s, workout), new Set(['warmup-remove-0']))
    expect(plan.warmup).toEqual([])
    expect(plan.movementsChanged).toBe(true)
  })

  it('a planned movement done for a different amount is offered, ticked', () => {
    const s = start()
    const longer = changeMovement(s, 'warmup', s.warmup![0].key, { amount: '10 min' })
    expect(labels(planChanges(longer, workout))).toEqual([['Easy cardio: 10 min (was 5 min)', true]])
    const plan = applyChanges(workout, planChanges(longer, workout), new Set(['warmup-amount-0']))
    expect(plan.warmup).toEqual([{ name: 'Easy cardio', reps: null, duration_seconds: 600 }])
  })

  it('the cardio from "Warm up first" is not offered, as a new movement or a new time', () => {
    const plain = { ...workout, warmup: [] }
    const s = recordCardio(startFromWorkout(plain, 'Workout 2', 'p1', [], new Date(2026, 9, 4)), new Date(2026, 9, 4))
    expect(s.warmup?.[0]).toMatchObject({ name: 'Easy cardio', done: true })
    expect(planChanges(s, plain)).toEqual([])

    // The planned cardio, stopped at 3 of its 5 minutes by the timer.
    const planned = startFromWorkout(workout, 'Workout 2', 'p1', [], new Date(2026, 9, 4, 10, 0))
    const timed = recordCardio({ ...planned, cardioStartedAt: new Date(2026, 9, 4, 10, 0).toISOString() }, new Date(2026, 9, 4, 10, 3))
    expect(timed.warmup?.[0]).toMatchObject({ amount: '3 min', done: true })
    expect(planChanges(timed, workout)).toEqual([])
  })

  it('a new order is offered unticked and applied in place', () => {
    const s = start()
    const moved = moveExercise(s, s.exercises[2].key, -1) // Squat, Calf raise, Shoulder Press
    expect(labels(planChanges(moved, workout))).toEqual([['Change the order: Squat, Calf raise, Shoulder Press', false]])
    const plan = applyChanges(workout, planChanges(moved, workout), new Set(['order']))
    expect(plan.exercises.map((e) => e.name)).toEqual(['Squat', 'Calf raise', 'Shoulder Press'])
    expect(plan.exercisesChanged).toBe(true)
  })

  it('an exercise skipped in the session keeps its place when the order changes', () => {
    let s = start()
    s = removeExercise(s, s.exercises[1].key) // Squat, Calf raise
    s = moveExercise(s, s.exercises[1].key, -1) // Calf raise, Squat
    const changes = planChanges(s, workout)
    expect(labels(changes)).toEqual([['Change the order: Calf raise, Squat', false], ['Remove Shoulder Press', false]])
    expect(applyChanges(workout, changes, new Set(['order'])).exercises.map((e) => e.name))
      .toEqual(['Calf raise', 'Shoulder Press', 'Squat'])
    expect(applyChanges(workout, changes, new Set(['order', 'remove-1'])).exercises.map((e) => e.name))
      .toEqual(['Calf raise', 'Squat'])
  })

  it('an exercise added in the session does not count as a new order', () => {
    const added = addExercise(start())
    let s = updateExercise(added.session, added.exKey, { name: 'Face pulls', naming: false })
    s = moveExercise(s, added.exKey, -1)
    s = moveExercise(s, added.exKey, -1) // Squat, Face pulls, Shoulder Press, Calf raise
    expect(planChanges(s, workout).some((c) => c.type === 'order')).toBe(false)
  })

  it('moving past either end changes nothing', () => {
    const s = start()
    expect(moveExercise(s, s.exercises[0].key, -1)).toBe(s)
    expect(moveExercise(s, s.exercises[2].key, 1)).toBe(s)
  })

  it('applies only the chosen changes', () => {
    let s = start()
    s = removeExercise(s, s.exercises[2].key)
    const added = addExercise(s)
    s = updateExercise(added.session, added.exKey, { name: 'Face pulls', naming: false })
    const set = addSet(s, added.exKey)
    s = toggleDone(set.session, set.setKey)
    const changes = planChanges(s, workout)
    const plan = applyChanges(workout, changes, new Set([`add-${added.exKey}`]))
    expect(plan.exercises.map((e) => e.name)).toEqual(['Squat', 'Shoulder Press', 'Calf raise', 'Face pulls'])
    expect(plan.exercisesChanged).toBe(true)
    expect(plan.movementsChanged).toBe(false)
  })
})
