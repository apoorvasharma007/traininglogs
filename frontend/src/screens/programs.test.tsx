import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { planText, workoutName } from '@/lib/programs'
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
    deload: { days_since: 0, due: false, in_progress: 0 },
    workouts: [
      { id: 'w1', position: 1, name: 'Bench', last_done: '2026-09-28', warmup: [], cooldown: [], exercises: [
        { name: 'Squat', warmup_sets: 2, working_sets: 3, target_reps: 2, amrap: false, alternatives: [] },
      ] },
      { id: 'w2', position: 2, name: null, last_done: null, warmup: [], cooldown: [], exercises: [] },
    ],
    ...patch,
  }
}

describe('workout display', () => {
  it('names a workout by number and optional name', () => {
    expect(workoutName({ position: 1, name: 'Push' })).toBe('Push')
    expect(workoutName({ position: 2, name: null })).toBe('Workout 2')
    expect(workoutName({ position: 2, name: 'workout 2 ' })).toBe('Workout 2')
  })

  it('summarises a plan', () => {
    expect(planText({ name: 'Squat', warmup_sets: 2, working_sets: 3, target_reps: 2, amrap: false, alternatives: [] })).toBe('2 warm-up + 3 × 2')
    expect(planText({ name: 'Chinups', warmup_sets: 0, working_sets: 1, target_reps: null, amrap: true, alternatives: [] })).toBe('1 × max')
    expect(planText({ name: 'Row', warmup_sets: 0, working_sets: 3, target_reps: null, amrap: false, alternatives: [] })).toBe('3 sets')
  })
})

describe('Programs', () => {
  it('with no programs, New program offers to create your own', async () => {
    const calls = fakeApi({
      'GET /programs': [],
      'POST /programs': program({ workouts: [], next_workout_id: null }),
      'GET /programs/p1': program({ workouts: [], next_workout_id: null }),
    })
    const location = renderApp('/programs')
    expect(await screen.findByText('No programs yet')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'New program' }))
    const choice = await screen.findByRole('dialog', { name: 'New program' })
    expect(within(choice).getByRole('link', { name: 'From a Template' })).toHaveAttribute('href', expect.stringContaining('/programs/templates'))
    await userEvent.click(within(choice).getByRole('button', { name: 'Create Your Own' }))
    const sheet = (await screen.findByLabelText('Name')).closest('[role="dialog"]') as HTMLElement
    await userEvent.type(within(sheet).getByLabelText('Name'), 'Strength')
    await userEvent.click(within(sheet).getByRole('button', { name: 'Create' }))
    await waitFor(() => expect(location.history.at(-1)).toBe('/programs/p1'))
    expect(calls.find((c) => c.key === 'POST /programs')?.body).toEqual({ name: 'Strength' })
  })

  it('copies a template into your programs', async () => {
    const template = {
      id: '5x5', name: '5×5 strength', days: '3 days a week',
      workouts: [{ name: 'A', exercises: [{ name: 'Squat', warmup_sets: 2, working_sets: 5, target_reps: 5, amrap: false, alternatives: [] }] }],
    }
    const calls = fakeApi({
      'GET /templates': [template],
      'POST /templates/5x5/copy': program(),
      'GET /programs/p1': program(),
    })
    const location = renderApp('/programs/templates')
    await userEvent.click(await screen.findByRole('button', { name: /5×5 strength/ }))
    const sheet = await screen.findByRole('dialog', { name: '5×5 strength' })
    expect(within(sheet).getByText('2 warm-up + 5 × 5')).toBeInTheDocument()
    await userEvent.click(within(sheet).getByRole('button', { name: 'Add Program' }))
    await waitFor(() => expect(location.history.at(-1)).toBe('/programs/p1'))
    expect(calls.some((c) => c.key === 'POST /templates/5x5/copy')).toBe(true)
  })

  it('shows workouts in order and follows the program', async () => {
    const calls = fakeApi({
      'GET /programs/p1': program(),
      'POST /programs/p1/follow': program({ following: true }),
      'GET /programs': [program({ following: true })],
    })
    renderApp('/programs/p1')
    expect(await screen.findByText('Bench')).toBeInTheDocument()
    expect(screen.getByText('Workout 2')).toBeInTheDocument()
    expect(screen.getByText('Last done Mon 28 Sept')).toBeInTheDocument()
    expect(screen.queryByText('Next')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Follow This Program' }))
    expect(await screen.findByText('Next')).toBeInTheDocument()
    expect(screen.getByText('Following')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Follow This Program' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Stop Following' })).toBeInTheDocument()
    // Renaming, reordering, adding and deleting live behind Edit.
    expect(screen.queryByRole('button', { name: 'Delete Program' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }))
    expect(screen.getByRole('button', { name: 'Delete Program' })).toBeInTheDocument()
    expect(calls.some((c) => c.key === 'POST /programs/p1/follow')).toBe(true)
  })

  it('adds alternatives that take turns', async () => {
    const after = program()
    after.workouts[1].exercises = [{ name: 'Shoulder Press', warmup_sets: 0, working_sets: 3, target_reps: 5, amrap: false, alternatives: ['Bench press'] }]
    const calls = fakeApi({ 'GET /programs/p1': program(), 'PUT /workouts/w2/exercises': after, 'GET /programs': [after] })
    renderApp('/programs/p1/workouts/w2')
    // An empty workout offers to add exercises, which starts editing.
    expect(await screen.findByText('No exercises yet')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Add Exercises' }))
    expect(screen.queryByRole('button', { name: 'Add Exercises' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '+ Exercise' }))
    const sheet = await screen.findByRole('dialog', { name: 'Add Exercise' })
    await userEvent.type(within(sheet).getByLabelText('Exercise'), 'Shoulder Press')
    await userEvent.type(within(sheet).getByLabelText('Alternative exercise'), 'Bench press{Enter}')
    await userEvent.type(within(sheet).getByLabelText('Alternative exercise'), 'shoulder press{Enter}')
    expect(within(sheet).getAllByText('Bench press')).toHaveLength(1)
    await userEvent.click(within(sheet).getByRole('button', { name: 'Add Exercise' }))
    expect(calls.some((c) => c.key === 'PUT /workouts/w2/exercises')).toBe(false)
    await userEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    await waitFor(() => expect(calls.some((c) => c.key === 'PUT /workouts/w2/exercises')).toBe(true))
    const sent = calls.find((c) => c.key === 'PUT /workouts/w2/exercises')!.body as { exercises: { alternatives: string[] }[] }
    expect(sent.exercises[0].alternatives).toEqual(['Bench press'])
    expect(await screen.findByText('or Bench press')).toBeInTheDocument()
  })

  it('asks before deleting an exercise from a workout', async () => {
    const before = program()
    before.workouts[1].exercises = [
      { name: 'Squat', warmup_sets: 0, working_sets: 3, target_reps: 5, amrap: false, alternatives: [] },
      { name: 'Bench press', warmup_sets: 0, working_sets: 3, target_reps: 5, amrap: false, alternatives: [] },
    ]
    const calls = fakeApi({ 'GET /programs/p1': before, 'PUT /workouts/w2/exercises': before, 'GET /programs': [before] })
    renderApp('/programs/p1/workouts/w2')
    await userEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    await userEvent.click(screen.getByText('Bench press'))
    const sheet = await screen.findByRole('dialog', { name: 'Edit exercise' })
    await userEvent.click(within(sheet).getByRole('button', { name: 'Remove' }))
    expect(calls.some((c) => c.key === 'PUT /workouts/w2/exercises')).toBe(false)
    await userEvent.click(within(sheet).getByRole('button', { name: 'Tap again to remove' }))
    expect(calls.some((c) => c.key === 'PUT /workouts/w2/exercises')).toBe(false)
    await userEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    await waitFor(() => expect(calls.find((c) => c.key === 'PUT /workouts/w2/exercises')?.body).toEqual({
      exercises: [{ name: 'Squat', warmup_sets: 0, working_sets: 3, target_reps: 5, amrap: false, alternatives: [] }],
    }))
  })

  it('opens for viewing; Edit turns the title into the name field', async () => {
    const calls = fakeApi({ 'GET /programs/p1': program(), 'PATCH /workouts/w2': program(), 'GET /programs': [program()] })
    renderApp('/programs/p1/workouts/w2')
    expect(await screen.findByRole('heading', { name: 'Workout 2' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Workout name')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }))
    const name = screen.getByLabelText('Workout name')
    expect(name).toHaveValue('Workout 2')
    await userEvent.clear(name)
    await userEvent.type(name, 'Light')
    expect(calls.some((c) => c.key === 'PATCH /workouts/w2')).toBe(false)
    await userEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    await waitFor(() => expect(calls.find((c) => c.key === 'PATCH /workouts/w2')?.body).toEqual({ name: 'Light' }))
  })

  it('adds warm-up templates to a workout, one after another', async () => {
    const calls = fakeApi({ 'GET /programs/p1': program(), 'PUT /workouts/w2/movements': program(), 'GET /programs': [program()] })
    renderApp('/programs/p1/workouts/w2')
    await userEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    // The warm-up editor comes first; the cool-down one also offers Easy cardio.
    await userEvent.click(screen.getAllByRole('button', { name: '+ Easy cardio' })[0])
    await userEvent.click(screen.getByRole('button', { name: '+ Dynamic stretching' }))
    expect(calls.some((c) => c.key === 'PUT /workouts/w2/movements')).toBe(false)
    await userEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    const last = () => calls.filter((c) => c.key === 'PUT /workouts/w2/movements').at(-1)?.body as { warmup: { name: string }[] } | undefined
    await waitFor(() => expect(last()?.warmup.map((m) => m.name)).toEqual(
      ['Easy cardio', 'Arm circles', 'Leg swings', 'Hip circles', 'Walking lunges', 'Torso twists'],
    ))
  })

  it('Cancel throws a draft away, asking first when something changed', async () => {
    const calls = fakeApi({ 'GET /programs/p1': program(), 'GET /programs': [program()] })
    renderApp('/programs/p1/workouts/w2')
    await userEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    // Editing hides the tabs and the back arrow: Save or Cancel are the ways out.
    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Back to/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'No changes' })).toBeDisabled()

    await userEvent.clear(screen.getByLabelText('Workout name'))
    await userEvent.type(screen.getByLabelText('Workout name'), 'Light')
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    const sheet = await screen.findByRole('dialog', { name: 'Discard your changes?' })
    await userEvent.click(within(sheet).getByRole('button', { name: 'Discard Changes' }))

    expect(await screen.findByRole('heading', { name: 'Workout 2' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument()
    expect(calls.filter((c) => !c.key.startsWith('GET'))).toEqual([])
  })

  it('reorders and renames a program only on Save', async () => {
    const calls = fakeApi({
      'GET /programs/p1': program(), 'GET /programs': [program()],
      'PATCH /programs/p1': program({ name: 'Heavy' }), 'PUT /programs/p1/workout-order': program(),
    })
    renderApp('/programs/p1')
    await userEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    await userEvent.clear(screen.getByLabelText('Program name'))
    await userEvent.type(screen.getByLabelText('Program name'), 'Heavy')
    expect(calls.some((c) => c.key === 'PATCH /programs/p1')).toBe(false)
    await userEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    await waitFor(() => expect(calls.find((c) => c.key === 'PATCH /programs/p1')?.body).toEqual({ name: 'Heavy' }))
    expect(calls.some((c) => c.key === 'PUT /programs/p1/workout-order')).toBe(false)
  })

  it('asks before stopping following', async () => {
    const calls = fakeApi({ 'GET /programs/p1': program({ following: true }), 'GET /programs': [program({ following: true })], 'POST /programs/p1/unfollow': program() })
    renderApp('/programs/p1')
    await userEvent.click(await screen.findByRole('button', { name: 'Stop Following' }))
    const sheet = await screen.findByRole('dialog', { name: 'Stop following Strength?' })
    expect(calls.some((c) => c.key === 'POST /programs/p1/unfollow')).toBe(false)
    await userEvent.click(within(sheet).getByRole('button', { name: 'Stop Following' }))
    await waitFor(() => expect(calls.some((c) => c.key === 'POST /programs/p1/unfollow')).toBe(true))
  })

  it('asks before switching away from the followed program', async () => {
    const other = { ...program({ following: true }), id: 'p2', name: 'Starting Strength' }
    const calls = fakeApi({ 'GET /programs/p1': program(), 'GET /programs': [other, program()], 'POST /programs/p1/follow': program({ following: true }) })
    renderApp('/programs/p1')
    await screen.findByText('Workout 2')
    await waitFor(() => expect(calls.some((c) => c.key === 'GET /programs')).toBe(true))
    await userEvent.click(screen.getByRole('button', { name: 'Follow This Program' }))
    const sheet = await screen.findByRole('dialog', { name: 'Follow Strength?' })
    expect(sheet).toHaveTextContent("You'll stop following Starting Strength")
    await userEvent.click(within(sheet).getByRole('button', { name: 'Follow This Program' }))
    await waitFor(() => expect(calls.some((c) => c.key === 'POST /programs/p1/follow')).toBe(true))
  })

  it('adds an exercise to a workout plan', async () => {
    const after = program()
    after.workouts[1].exercises = [{ name: 'Deadlift', warmup_sets: 0, working_sets: 3, target_reps: 5, amrap: false, alternatives: [] }]
    const calls = fakeApi({
      'GET /programs/p1': program(),
      'PUT /workouts/w2/exercises': after,
      'GET /programs': [after],
    })
    renderApp('/programs/p1/workouts/w2')
    // An empty workout offers to add exercises, which starts editing.
    expect(await screen.findByText('No exercises yet')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Add Exercises' }))
    expect(screen.queryByRole('button', { name: 'Add Exercises' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '+ Exercise' }))
    const sheet = await screen.findByRole('dialog', { name: 'Add Exercise' })
    await userEvent.type(within(sheet).getByLabelText('Exercise'), 'Deadlift')
    // Reps start empty (as many as you can); typing a number sets a target.
    expect(within(sheet).getByLabelText('Target reps')).toHaveValue('')
    await userEvent.type(within(sheet).getByLabelText('Target reps'), '5')
    await userEvent.click(within(sheet).getByRole('button', { name: 'Add Exercise' }))
    await userEvent.click(screen.getByRole('button', { name: 'Save Changes' }))

    await waitFor(() => expect(screen.getByText('3 × 5')).toBeInTheDocument())
    expect(calls.find((c) => c.key === 'PUT /workouts/w2/exercises')?.body).toEqual({
      exercises: [{ name: 'Deadlift', warmup_sets: 0, working_sets: 3, target_reps: 5, amrap: false, alternatives: [] }],
    })
  })
})
