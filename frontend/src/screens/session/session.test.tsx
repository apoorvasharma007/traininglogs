import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { clear, get } from 'idb-keyval'
import { beforeEach, describe, expect, it } from 'vitest'
import { saveSession } from '@/lib/store'
import { startFromWorkout } from '@/lib/session'
import { fakeApi, renderApp } from '@/test-utils'

const workout = {
  id: 'w1', position: 1, name: 'Bench', last_done: null,
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

  it('shows last time and the pinned note, ticks a set and saves it at Finish', async () => {
    await seed()
    const calls = fakeApi({
      'GET /pins': [{ name_key: 'squat', note: 'Brace before each rep', pinned_at: '' }],
      'POST /sessions': { session_id: 's1', created: true },
      'GET /programs': [],
      'GET /programs/p1': { id: 'p1', name: 'Strength', deload_after_days: 28, following: true, following_since: null, next_workout_id: 'w1', workouts: [workout] },
    })
    const location = renderApp('/session')

    expect(await screen.findByText('better depth')).toBeInTheDocument()
    expect(await screen.findByText('Brace before each rep')).toBeInTheDocument()
    expect(screen.getByText('0 of 2 sets done · saved on this phone')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Set 1 done' }))
    expect(screen.getByText('1 of 2 sets done · saved on this phone')).toBeInTheDocument()
    // Saved on the phone straight away.
    await waitFor(async () => expect((await get('session-in-progress'))?.exercises[0].sets[0].done).toBe(true))

    await userEvent.click(screen.getByRole('button', { name: 'Finish' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Save session' }))
    await waitFor(() => expect(location.history.at(-1)).toBe('/session/done'))
    expect(await screen.findByText('Saved to your history.')).toBeInTheDocument()

    const sent = calls.find((c) => c.key === 'POST /sessions')?.body as { exercises: { sets: unknown[] }[]; program_workout_id: string }
    expect(sent.program_workout_id).toBe('w1')
    expect(sent.exercises[0].sets).toEqual([{ weight_kg: 125, reps: 2, rpe: null, notes: null }])
    expect(await get('session-in-progress')).toBeUndefined()
    expect(await get('sessions-to-send')).toEqual([])
  })

  it('keeps a finished session on the phone when it cannot be sent', async () => {
    await seed()
    fakeApi({ 'GET /pins': [], 'GET /programs': [] })
    const offline = globalThis.fetch
    globalThis.fetch = (async (url: string, init?: RequestInit) => {
      if (init?.method === 'POST') throw new TypeError('Failed to fetch')
      return offline(url, init)
    }) as typeof fetch

    renderApp('/session')
    await userEvent.click(await screen.findByRole('button', { name: 'Set 1 done' }))
    await userEvent.click(screen.getByRole('button', { name: 'Finish' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Save session' }))

    // Two send attempts can overlap (the one at Finish and the one when the app opened), so the
    // status may flick to "Sending…" before it settles; wait for the settled screen.
    await waitFor(() => expect(screen.getByText('Waiting to send')).toBeInTheDocument())
    const queued = (await get('sessions-to-send')) as { client_id: string }[]
    expect(queued).toHaveLength(1)
  })

  it('takes a typed weight over last time and keeps it on the phone', async () => {
    await seed()
    fakeApi({ 'GET /pins': [] })
    renderApp('/session')
    const weight = await screen.findByLabelText('Weight for set 1')
    // Last time's value is a grey hint until something is typed.
    expect(weight).toHaveValue('')
    expect(weight).toHaveAttribute('placeholder', '125')
    await userEvent.type(weight, '127.5')
    expect(screen.getByLabelText('Reps for set 1')).toHaveValue('2')
    await waitFor(async () => expect((await get('session-in-progress'))?.exercises[0].sets[0].weight).toBe('127.5'))
  })

  it('will not finish with nothing ticked', async () => {
    await seed()
    fakeApi({ 'GET /pins': [] })
    renderApp('/session')
    await userEvent.click(await screen.findByRole('button', { name: 'Finish' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Save session' }))
    expect(await screen.findByText('Tick at least one set first. Unticked sets are not saved.')).toBeInTheDocument()
  })

  it('adds an exercise as a blank card with a name field', async () => {
    await seed()
    fakeApi({ 'GET /pins': [] })
    renderApp('/session')
    await userEvent.click(await screen.findByRole('button', { name: '+ Exercise' }))
    const name = await screen.findByLabelText('Exercise name')
    await userEvent.type(name, 'Deadlift{Enter}')
    expect(await screen.findByRole('heading', { name: 'Deadlift' })).toBeInTheDocument()
  })
})
