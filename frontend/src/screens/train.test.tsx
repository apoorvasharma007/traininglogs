import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { clear, get, set } from 'idb-keyval'
import { beforeEach, describe, expect, it } from 'vitest'
import { startBlank } from '@/lib/session'
import { saveSession as store } from '@/lib/store'
import type { Program } from '@/lib/types'
import { fakeApi, renderApp } from '@/test-utils'

function program(patch: Partial<Program> = {}): Program {
  return {
    id: 'p1', name: 'Bodybuilding Transformation · Ramp-up', deload_after_days: 28, following: true,
    following_since: '2026-09-01', next_workout_id: 'w2',
    deload: { days_since: 3, due: false, in_progress: 0 },
    workouts: [
      { id: 'w1', position: 1, name: 'Upper Strength', last_done: null, warmup: [], cooldown: [], exercises: [] },
      { id: 'w2', position: 2, name: 'Lower Strength', last_done: null, warmup: [], cooldown: [], exercises: [
        { name: 'Seated Leg Hamstring Curl', warmup_sets: 2, working_sets: 3, target_reps: 12, amrap: false, alternatives: [] },
      ] },
    ],
    ...patch,
  }
}

describe('Train', () => {
  beforeEach(async () => {
    await clear()
    Object.keys(localStorage).filter((k) => k !== 'tl_session').forEach((k) => localStorage.removeItem(k)) // keep the sign-in
  })

  it('shows the program you follow and starts its next workout', async () => {
    const calls = fakeApi({
      'GET /programs': [program()],
      'GET /exercises/last?name=Seated%20Leg%20Hamstring%20Curl': [],
    })
    const location = renderApp('/')
    expect(await screen.findByText('Bodybuilding Transformation · Ramp-up')).toBeInTheDocument()
    expect(screen.getByText('2 · Lower Strength')).toBeInTheDocument()
    // A summary: exercise names only, no sets.
    expect(screen.queryByText(/× 12/)).not.toBeInTheDocument()
    expect(screen.queryByText(/more$/)).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Start workout' }))
    await waitFor(() => expect(location.history.at(-1)).toBe('/session'))
    const started = await get('session-in-progress')
    expect(started.workoutId).toBe('w2')
    expect(calls.some((c) => c.key.startsWith('GET /exercises/last'))).toBe(true)
  })

  it('lists the first 5 exercises and counts the rest', async () => {
    const many = program()
    many.workouts[1].exercises = Array.from({ length: 8 }, (_, i) => ({ name: `Exercise ${i + 1}`, warmup_sets: 0, working_sets: 3, target_reps: 10, amrap: false, alternatives: [] }))
    fakeApi({ 'GET /programs': [many] })
    renderApp('/')
    expect(await screen.findByText('Exercise 5')).toBeInTheDocument()
    expect(screen.queryByText('Exercise 6')).not.toBeInTheDocument()
    expect(screen.getByText('+3 more')).toBeInTheDocument()
  })

  it('without a program, offers recent sessions to do again', async () => {
    fakeApi({
      'GET /programs': [program({ following: false })],
      'GET /sessions?limit=3': [{ session_id: 's1', date: '2026-10-02', program: null, focus: null, exercises: ['Squat', 'Bench press'] }],
    })
    renderApp('/')
    expect(await screen.findByText('Squat · Bench press')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Do again' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Or follow a program' })).toBeInTheDocument()
  })

  it('a deload reminder is only a reminder: OK hides it', async () => {
    fakeApi({ 'GET /programs': [program({ deload: { days_since: 29, due: true, in_progress: 0 } })] })
    renderApp('/')
    expect(await screen.findByText('Deload due')).toBeInTheDocument()
    expect(screen.getByText(/4 weeks of training/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'OK' }))
    expect(screen.queryByText('Deload due')).not.toBeInTheDocument()
  })

  it('makes Log from notes easy to find, with ad-hoc last', async () => {
    fakeApi({ 'GET /programs': [program()] })
    renderApp('/')
    expect(await screen.findByText('Wrote it down instead?')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Log from notes' })).toHaveAttribute('href', '/log')
    const links = screen.getAllByRole('link').concat(screen.getAllByRole('button')).map((e) => e.textContent)
    expect(links).toContain('Repeat a past session')
    expect(links).toContain('Ad-hoc workout')
  })

  it('offers to resume a session in progress', async () => {
    await store(startBlank(new Date(2026, 9, 4, 10, 5)))
    fakeApi({ 'GET /programs': [program()] })
    renderApp('/')
    expect(await screen.findByText('Session in progress')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Resume/ })).toHaveAttribute('href', '/session')
    expect(screen.queryByRole('button', { name: 'Start workout' })).not.toBeInTheDocument()
  })

  it('says when finished sessions are waiting to send', async () => {
    await set('sessions-to-send', [{ client_id: 'a' }])
    fakeApi({ 'GET /programs': [] })
    globalThis.fetch = (async (_url: string, init?: RequestInit) => {
      if (init?.method === 'POST') throw new TypeError('Failed to fetch')
      return new Response('[]', { status: 200 })
    }) as typeof fetch
    renderApp('/')
    expect(await screen.findByText('1 session waiting to send')).toBeInTheDocument()
  })
})
