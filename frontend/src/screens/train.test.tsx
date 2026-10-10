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
    expect(screen.getByText('Lower Strength')).toBeInTheDocument()
    // A summary: exercise names only, no sets.
    expect(screen.queryByText(/× 12/)).not.toBeInTheDocument()
    expect(screen.queryByText(/more$/)).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Start Workout' }))
    await waitFor(() => expect(location.history.at(-1)).toBe('/session'))
    const started = await get('session-in-progress:a@example.com')
    expect(started.workoutId).toBe('w2')
    expect(calls.some((c) => c.key.startsWith('GET /exercises/last'))).toBe(true)
  })

  it('shows Starting… and takes no second tap while last time is fetched', async () => {
    fakeApi({ 'GET /programs': [program()] })
    // Last time's sets take a while to come back.
    const fake = globalThis.fetch
    let lastCalls = 0
    let answer: (r: Response) => void = () => {}
    globalThis.fetch = ((url: string, init?: RequestInit) => {
      if (!String(url).startsWith('/exercises/last')) return fake(url, init)
      lastCalls += 1
      return new Promise<Response>((r) => { answer = r })
    }) as typeof fetch
    renderApp('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Start Workout' }))
    const button = await screen.findByRole('button', { name: 'Starting…' })
    expect(button).toBeDisabled()
    await userEvent.click(button)
    expect(lastCalls).toBe(1)
    answer(new Response('[]', { status: 200 }))
  })

  it('lists the first 4 exercises and counts the rest', async () => {
    const many = program()
    many.workouts[1].exercises = Array.from({ length: 8 }, (_, i) => ({ name: `Exercise ${i + 1}`, warmup_sets: 0, working_sets: 3, target_reps: 10, amrap: false, alternatives: [] }))
    fakeApi({ 'GET /programs': [many] })
    renderApp('/')
    expect(await screen.findByText('Exercise 4')).toBeInTheDocument()
    expect(screen.queryByText('Exercise 5')).not.toBeInTheDocument()
    expect(screen.getByText('+4 more')).toBeInTheDocument()
  })

  it('without a program, nudges toward one', async () => {
    fakeApi({ 'GET /programs': [program({ following: false })] })
    renderApp('/')
    expect(await screen.findByText('Start with a Program')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Browse Templates' })).toHaveAttribute('href', '/programs/templates')
    // Create Your Own goes straight to naming the new program.
    fakeApi({ 'GET /programs': [program({ following: false })] })
    await userEvent.click(screen.getByRole('link', { name: 'Create Your Own' }))
    expect(await screen.findByRole('dialog', { name: 'New Program' })).toBeInTheDocument()
  })

  it('a deload reminder is only a reminder: OK hides it', async () => {
    fakeApi({ 'GET /programs': [program({ deload: { days_since: 29, due: true, in_progress: 0 } })] })
    renderApp('/')
    expect(await screen.findByText('Deload Due')).toBeInTheDocument()
    expect(screen.getByText(/4 weeks of training/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'OK' }))
    expect(screen.queryByText('Deload Due')).not.toBeInTheDocument()
  })

  it('offers an ad-hoc workout, notes, and repeating a past session', async () => {
    fakeApi({ 'GET /programs': [program()] })
    renderApp('/')
    expect(await screen.findByRole('button', { name: /Ad-hoc Workout/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Wrote it down instead\?/ })).toHaveAttribute('href', '/log')
    expect(screen.getByRole('link', { name: 'Repeat a Past Session' })).toHaveAttribute('href', '/history')
  })

  it('offers to resume a session in progress', async () => {
    await store(startBlank(new Date(2026, 9, 4, 10, 5)))
    fakeApi({ 'GET /programs': [program()] })
    renderApp('/')
    expect(await screen.findByText('Session in Progress')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Resume/ })).toHaveAttribute('href', '/session')
    expect(screen.queryByRole('button', { name: 'Start Workout' })).not.toBeInTheDocument()
  })

  it('says when finished sessions are waiting to send', async () => {
    await set('sessions-to-send:a@example.com', [{ client_id: 'a' }])
    fakeApi({ 'GET /programs': [] })
    globalThis.fetch = (async (_url: string, init?: RequestInit) => {
      if (init?.method === 'POST') throw new TypeError('Failed to fetch')
      return new Response('[]', { status: 200 })
    }) as typeof fetch
    renderApp('/')
    expect(await screen.findByText('1 session waiting to send')).toBeInTheDocument()
  })

  it("never shows or sends someone else's sessions left on this phone", async () => {
    await set('sessions-to-send:b@example.com', [{ client_id: 'theirs' }])
    await set('session-in-progress:b@example.com', startBlank(new Date(2026, 9, 4, 10, 5)))
    const calls = fakeApi({ 'GET /programs': [program()] })
    renderApp('/')
    expect(await screen.findByRole('button', { name: 'Start Workout' })).toBeInTheDocument()
    expect(screen.queryByText('Session in Progress')).not.toBeInTheDocument()
    expect(screen.queryByText(/waiting to send/)).not.toBeInTheDocument()
    expect(calls.filter((c) => c.key === 'POST /sessions')).toEqual([])
  })
})
