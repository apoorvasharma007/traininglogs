import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { planText, workoutTitle } from '@/lib/programs'
import type { Program } from '@/lib/types'
import { fakeApi, renderApp } from '@/test-utils'

function program(patch: Partial<Program> = {}): Program {
  return {
    id: 'p1',
    name: 'Strength',
    deload_after_days: 28,
    following: false,
    following_since: null,
    next_workout_id: 'w1',
    workouts: [
      { id: 'w1', position: 1, name: 'Bench', last_done: '2026-09-28', exercises: [
        { name: 'Squat', warmup_sets: 2, working_sets: 3, target_reps: 2, amrap: false },
      ] },
      { id: 'w2', position: 2, name: null, last_done: null, exercises: [] },
    ],
    ...patch,
  }
}

describe('workout display', () => {
  it('names a workout by number and optional name', () => {
    expect(workoutTitle({ position: 1, name: 'Push' })).toBe('1 · Push')
    expect(workoutTitle({ position: 2, name: null })).toBe('Workout 2')
  })

  it('summarises a plan', () => {
    expect(planText({ name: 'Squat', warmup_sets: 2, working_sets: 3, target_reps: 2, amrap: false })).toBe('2 warmup · 3 × 2')
    expect(planText({ name: 'Chinups', warmup_sets: 0, working_sets: 1, target_reps: null, amrap: true })).toBe('1 × max')
    expect(planText({ name: 'Row', warmup_sets: 0, working_sets: 3, target_reps: null, amrap: false })).toBe('3 sets')
  })
})

describe('Programs', () => {
  it('explains programs when there are none, and creates one', async () => {
    const calls = fakeApi({
      'GET /programs': [],
      'POST /programs': program({ workouts: [], next_workout_id: null }),
      'GET /programs/p1': program({ workouts: [], next_workout_id: null }),
    })
    const location = renderApp('/programs')
    expect(await screen.findByText('No programs yet')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'New' }))
    const sheet = await screen.findByRole('dialog', { name: 'New program' })
    await userEvent.type(within(sheet).getByLabelText('Name'), 'Strength')
    await userEvent.click(within(sheet).getByRole('button', { name: 'Create' }))
    await waitFor(() => expect(location.history.at(-1)).toBe('/programs/p1'))
    expect(calls.find((c) => c.key === 'POST /programs')?.body).toEqual({ name: 'Strength' })
  })

  it('shows workouts in order and follows the program', async () => {
    const calls = fakeApi({
      'GET /programs/p1': program(),
      'POST /programs/p1/follow': program({ following: true }),
      'GET /programs': [program({ following: true })],
    })
    renderApp('/programs/p1')
    expect(await screen.findByText('1 · Bench')).toBeInTheDocument()
    expect(screen.getByText('Workout 2')).toBeInTheDocument()
    expect(screen.getByText('Last done Mon 28 Sept')).toBeInTheDocument()
    expect(screen.queryByText('Next')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Follow this program' }))
    expect(await screen.findByText('Next')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Stop following' })).toBeInTheDocument()
    expect(calls.some((c) => c.key === 'POST /programs/p1/follow')).toBe(true)
  })

  it('adds an exercise to a workout plan', async () => {
    const after = program()
    after.workouts[1].exercises = [{ name: 'Deadlift', warmup_sets: 0, working_sets: 3, target_reps: 5, amrap: false }]
    const calls = fakeApi({
      'GET /programs/p1': program(),
      'PUT /workouts/w2/exercises': after,
      'GET /programs': [after],
    })
    renderApp('/programs/p1/workouts/w2')
    await userEvent.click(await screen.findByRole('button', { name: '+ Exercise' }))
    const sheet = await screen.findByRole('dialog', { name: 'Add exercise' })
    await userEvent.type(within(sheet).getByLabelText('Exercise'), 'Deadlift')
    await userEvent.click(within(sheet).getByRole('button', { name: 'Add' }))

    expect(await screen.findByText('Deadlift')).toBeInTheDocument()
    expect(screen.getByText('3 × 5')).toBeInTheDocument()
    expect(calls.find((c) => c.key === 'PUT /workouts/w2/exercises')?.body).toEqual({
      exercises: [{ name: 'Deadlift', warmup_sets: 0, working_sets: 3, target_reps: 5, amrap: false }],
    })
  })
})
