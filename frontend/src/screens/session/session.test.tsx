import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { clear, get, set } from 'idb-keyval'
import { beforeEach, describe, expect, it } from 'vitest'
import { saveSession } from '@/lib/store'
import { startFromWorkout } from '@/lib/session'
import { clearLastFinished, type Finished } from '@/screens/session/finished'
import { fakeApi, renderApp } from '@/test-utils'

const workout = {
  id: 'w1', position: 1, name: 'Bench', last_done: null, warmup: [], cooldown: [],
  exercises: [{ name: 'Squat', warmup_sets: 0, working_sets: 2, target_reps: 2, amrap: false, alternatives: [] }],
}
const lasts = [{ name: 'Squat', date: '2026-10-02', notes: 'better depth', warmup_sets: [], sets: [{ weight_kg: 125, reps: 2, notes: null }] }]

async function seed() {
  await saveSession(startFromWorkout(workout, '1 · Bench', 'p1', lasts, new Date(2026, 9, 4, 10, 0)))
}

describe('Session', () => {
  beforeEach(async () => {
    await clear()
  })

  it('after a restart on the Done screen, brings back the summary and the program offer', async () => {
    await clearLastFinished() // the app's memory, as after a restart
    const finished: Finished = {
      clientId: 'c1', title: '1 · Bench', minutes: 40, sets: 3, programId: 'p1', workoutId: 'w1', workout,
      changes: [{ id: 'sets-0', type: 'sets', index: 0, warmup_sets: 0, working_sets: 3, label: 'Squat: 3 working sets (was 2)', on: true }],
    }
    await set('last-finished', finished)
    const program = { id: 'p1', name: 'Strength', deload_after_days: 28, following: true, following_since: null, next_workout_id: 'w1',
      deload: { days_since: 0, due: false, in_progress: 0 }, workouts: [workout] }
    fakeApi({ 'GET /programs/p1': program })
    const location = renderApp('/session/done')
    expect(await screen.findByText('40 min')).toBeInTheDocument()
    expect(screen.getByText('3 sets')).toBeInTheDocument()
    expect(screen.getByText('Update the program?')).toBeInTheDocument()

    // Kept as is: remembered, so a second restart doesn't ask again.
    await userEvent.click(screen.getByRole('button', { name: 'Keep as Is' }))
    await waitFor(async () => expect((await get('last-finished'))?.answered).toBe(true))

    await userEvent.click(screen.getByRole('link', { name: 'Done' }))
    await waitFor(() => expect(location.history.at(-1)).toBe('/'))
    expect(await get('last-finished')).toBeUndefined()
  })

  it('the Done screen with nothing finished goes to Train', async () => {
    await clearLastFinished()
    fakeApi({ 'GET /programs': [] })
    const location = renderApp('/session/done')
    await waitFor(() => expect(location.history.at(-1)).toBe('/'))
  })

  it('shows last time, ticks a set and saves it at Finish', async () => {
    await seed()
    const calls = fakeApi({
      'POST /sessions': { session_id: 's1', created: true },
      'GET /programs': [],
      'GET /programs/p1': { id: 'p1', name: 'Strength', deload_after_days: 28, following: true, following_since: null, next_workout_id: 'w1', workouts: [workout] },
    })
    const location = renderApp('/session')

    expect(await screen.findByText('better depth')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Set 1 done' }))
    expect(screen.getByRole('button', { name: 'Set 1 done' })).toHaveAttribute('aria-pressed', 'true')
    // Saved on the phone straight away.
    await waitFor(async () => expect((await get('session-in-progress:a@example.com'))?.exercises[0].sets[0].done).toBe(true))

    await userEvent.click(screen.getByRole('button', { name: 'Finish' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Save Session' }))
    await waitFor(() => expect(location.history.at(-1)).toBe('/session/done'))
    expect(await screen.findByText('Saved to your history.')).toBeInTheDocument()

    const sent = calls.find((c) => c.key === 'POST /sessions')?.body as { exercises: { sets: unknown[] }[]; program_workout_id: string }
    expect(sent.program_workout_id).toBe('w1')
    expect(sent.exercises[0].sets).toEqual([{ weight_kg: 125, reps: 2, rpe: null, notes: null }])
    expect(await get('session-in-progress:a@example.com')).toBeUndefined()
    expect(await get('sessions-to-send:a@example.com')).toEqual([])
  })

  it("offers to save a session's changes to the program", async () => {
    await seed()
    const program = { id: 'p1', name: 'Strength', deload_after_days: 28, following: true, following_since: null, next_workout_id: 'w1',
      deload: { days_since: 0, due: false, in_progress: 0 }, workouts: [workout] }
    const calls = fakeApi({
      'GET /programs': [program], 'GET /programs/p1': program,
      'POST /sessions': { session_id: 's1', created: true }, 'PUT /workouts/w1/exercises': program,
    })
    renderApp('/session')
    await userEvent.click(await screen.findByRole('button', { name: 'Set 1 done' }))
    await userEvent.click(screen.getByRole('button', { name: '+ Set' }))
    // An extra set counts toward the plan only once it's done.
    const sets = screen.getAllByRole('button', { name: /^Set \d done$/ })
    await userEvent.click(sets[sets.length - 1])
    await userEvent.click(screen.getByRole('button', { name: 'Finish' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Save Session' }))

    expect(await screen.findByText('Update the program?')).toBeInTheDocument()
    expect(screen.getByLabelText('Squat: 3 working sets (was 2)')).toBeChecked()
    await userEvent.click(screen.getByRole('button', { name: 'Update Program' }))
    // Nothing is written until the reminder is confirmed.
    const reminder = await screen.findByRole('dialog', { name: 'Update Bench?' })
    expect(reminder).toHaveTextContent('every session of Bench from now on')
    expect(calls.some((c) => c.key === 'PUT /workouts/w1/exercises')).toBe(false)
    await userEvent.click(within(reminder).getByRole('button', { name: 'Update Program' }))
    expect(await screen.findByText('Program updated.')).toBeInTheDocument()
    const saved = calls.find((c) => c.key === 'PUT /workouts/w1/exercises')!.body as { exercises: { working_sets: number }[] }
    expect(saved.exercises[0].working_sets).toBe(3)
  })

  it('keeps a finished session on the phone when it cannot be sent', async () => {
    await seed()
    fakeApi({ 'GET /programs': [] })
    const offline = globalThis.fetch
    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      if (init?.method === 'POST') throw new TypeError('Failed to fetch')
      return offline(url, init)
    }) as typeof fetch

    renderApp('/session')
    await userEvent.click(await screen.findByRole('button', { name: 'Set 1 done' }))
    await userEvent.click(screen.getByRole('button', { name: 'Finish' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Save Session' }))

    // Two send attempts can overlap (the one at Finish and the one when the app opened), so the
    // status may flick to "Sending…" before it settles; wait for the settled screen.
    await waitFor(() => expect(screen.getByText('Waiting to send')).toBeInTheDocument())
    const queued = (await get('sessions-to-send:a@example.com')) as { client_id: string }[]
    expect(queued).toHaveLength(1)
  })

  it('takes a typed weight over last time and keeps it on the phone', async () => {
    await seed()
    fakeApi({})
    renderApp('/session')
    const weight = await screen.findByLabelText('Weight for set 1')
    // Last time's value is a grey hint until something is typed.
    expect(weight).toHaveValue('')
    expect(weight).toHaveAttribute('placeholder', '125')
    await userEvent.type(weight, '127.5')
    expect(screen.getByLabelText('Reps for set 1')).toHaveValue('2')
    await waitFor(async () => expect((await get('session-in-progress:a@example.com'))?.exercises[0].sets[0].weight).toBe('127.5'))
  })

  it('switches an exercise to an alternative from the swap icon', async () => {
    await saveSession(startFromWorkout(
      { ...workout, exercises: [{ name: 'Shoulder Press', warmup_sets: 0, working_sets: 1, target_reps: 5, amrap: false, alternatives: ['Bench press'] }] },
      '1 · Bench', 'p1',
      [{ name: 'Bench press', date: '2026-10-02', notes: 'still hard', warmup_sets: [], sets: [{ weight_kg: 90, reps: 2, notes: null }] }],
      new Date(2026, 9, 4, 10, 0)))
    fakeApi({})
    renderApp('/session')
    await userEvent.click(await screen.findByRole('button', { name: 'Switch Shoulder Press to an alternative' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Bench press' }))
    expect(await screen.findByRole('heading', { name: /Bench press/ })).toBeInTheDocument()
    expect(screen.getByLabelText('Weight for set 1')).toHaveAttribute('placeholder', '90')
    expect(screen.getByText('still hard')).toBeInTheDocument()
  })

  it('collapses an exercise when its last set is ticked, and opens it again on tap', async () => {
    await saveSession(startFromWorkout(
      { ...workout, exercises: [
        { name: 'Squat', warmup_sets: 0, working_sets: 1, target_reps: 2, amrap: false, alternatives: [] },
        { name: 'Bench press', warmup_sets: 0, working_sets: 1, target_reps: 2, amrap: false, alternatives: [] },
      ] },
      '1 · Bench', 'p1', [], new Date(2026, 9, 4, 10, 0)))
    fakeApi({})
    renderApp('/session')
    await screen.findByRole('button', { name: 'Options for Squat' })
    await userEvent.click(screen.getAllByRole('button', { name: 'Set 1 done' })[0])

    const collapsed = await screen.findByRole('button', { name: 'Squat: all 1 set done. Show sets' })
    expect(screen.queryAllByRole('button', { name: 'Set 1 done' })).toHaveLength(1)

    await userEvent.click(collapsed)
    expect(screen.getAllByRole('button', { name: 'Set 1 done' })).toHaveLength(2)
  })

  it('fills the warmup sets from a ramp', async () => {
    await seed()
    fakeApi({})
    renderApp('/session')
    await userEvent.click(await screen.findByRole('button', { name: 'Options for Squat' }))
    // Warm-up set templates sit at the bottom of the menu, just above Remove Exercise.
    const items = (await screen.findAllByRole('button')).map((b) => b.textContent)
    expect(items.indexOf('Warm-up Set Templates')).toBe(items.indexOf('Remove Exercise') - 1)
    await userEvent.click(screen.getByRole('button', { name: 'Warm-up Set Templates' }))
    expect(await screen.findByText('Builds up to your first working set, 125 kg.')).toBeInTheDocument()
    await userEvent.click(await screen.findByRole('button', { name: /Short ramp/ }))
    // Built up to the first working set's 125 kg: 62.5 x 5, 87.5 x 4, 112.5 x 2.
    await waitFor(async () => expect((await get('session-in-progress:a@example.com'))?.exercises[0].sets.filter((x: { kind: string }) => x.kind === 'warmup')
      .map((x: { weight: string; reps: string }) => [x.weight, x.reps])).toEqual([['62.5', '5'], ['87.5', '4'], ['112.5', '2']]))
  })

  it('moves an exercise with Move Down', async () => {
    await saveSession(startFromWorkout(
      { ...workout, exercises: [...workout.exercises, { name: 'Bench press', warmup_sets: 0, working_sets: 1, target_reps: 5, amrap: false, alternatives: [] }] },
      '1 · Bench', 'p1', lasts, new Date(2026, 9, 4, 10, 0),
    ))
    fakeApi({})
    renderApp('/session')
    await userEvent.click(await screen.findByRole('button', { name: 'Options for Squat' }))
    const menu = await screen.findByRole('dialog', { name: 'Exercise options' })
    await userEvent.click(within(menu).getByRole('button', { name: 'Move Down' }))
    await waitFor(async () => expect((await get('session-in-progress:a@example.com'))?.exercises.map((e: { name: string }) => e.name))
      .toEqual(['Bench press', 'Squat']))
  })

  it('nudges a warm-up first; Done records 5 minutes of easy cardio', async () => {
    await seed()
    fakeApi({})
    renderApp('/session')
    expect(await screen.findByText('Warm up first')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Start' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Done' }))
    expect(screen.queryByText('Warm up first')).not.toBeInTheDocument()
    await waitFor(async () => {
      const saved = await get('session-in-progress:a@example.com')
      expect(saved.warmup.map((m: { name: string; amount: string; done: boolean }) => [m.name, m.amount, m.done])).toEqual([['Easy cardio', '1 min', true]])
    })
  })

  it('lets the warm-up nudge be dismissed', async () => {
    await seed()
    fakeApi({})
    renderApp('/session')
    await userEvent.click(await screen.findByRole('button', { name: 'Skip the warm-up' }))
    expect(screen.queryByText('Warm up first')).not.toBeInTheDocument()
    await waitFor(async () => expect((await get('session-in-progress:a@example.com')).warmupNudge).toBe('skipped'))
  })

  it('will not finish with nothing ticked', async () => {
    await seed()
    fakeApi({})
    renderApp('/session')
    await userEvent.click(await screen.findByRole('button', { name: 'Finish' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Save Session' }))
    expect(await screen.findByText('Tick at least one set first. Unticked sets are not saved.')).toBeInTheDocument()
  })

  it('adds an exercise as a blank card with a name field', async () => {
    await seed()
    fakeApi({})
    renderApp('/session')
    await userEvent.click(await screen.findByRole('button', { name: '+ Exercise' }))
    const name = await screen.findByLabelText('Exercise name')
    await userEvent.type(name, 'Deadlift{Enter}')
    expect(await screen.findByRole('heading', { name: 'Deadlift' })).toBeInTheDocument()
  })
})
