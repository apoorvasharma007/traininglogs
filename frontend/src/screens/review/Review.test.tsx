import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Card } from '@/lib/types'
import { fakeApi, renderApp } from '@/test-utils'

function card(weight: number, withSet = true): Card {
  return {
    session_header: { date: '2026-10-04', focus: 'Strength', program: null, duration_minutes: null, uncertain_fields: [], path: '' },
    warnings: [],
    exercises: [
      {
        header: { number: 1, name: 'Squat', failed: false, path: 'exercises.0' },
        warmup_rows: [{ number: 1, weight_kg: 80, rep_count: null, notes: null, uncertain_fields: [], path: 'exercises.0.warmup_sets.0' }],
        working_set_rows: withSet
          ? [{ number: 1, weight_kg: weight, reps: '2', rpe: null, notes: null, uncertain_fields: [], path: 'exercises.0.sets.0' }]
          : [],
        note_preview: null,
        failure_reason: null,
      },
    ],
  }
}

const reply = (c: Card) => ({ extract: { v: 'next' }, card: c, correction: { source: 'manual' }, created_path: null })

describe('Review', () => {
  it('types a weight into the set row and sends only that change', async () => {
    const calls = fakeApi({
      'GET /extractions/x1': card(120),
      'POST /extractions/x1/edit': reply(card(122.5)),
    })
    renderApp('/review/x1')
    const weight = await screen.findByLabelText('Weight for set 1')
    expect(weight).toHaveValue('120')
    await userEvent.clear(weight)
    await userEvent.type(weight, '122.5')
    await userEvent.tab()

    await waitFor(() => expect(calls.at(-1)).toEqual({
      key: 'POST /extractions/x1/edit',
      body: { edits: [{ path: 'exercises.0.sets.0', field: 'weight_kg', value: 122.5 }] },
    }))
    expect(await screen.findByLabelText('Weight for set 1')).toHaveValue('122.5')
  })

  it('sends nothing when a box is left unchanged', async () => {
    const calls = fakeApi({ 'GET /extractions/x1': card(120) })
    renderApp('/review/x1')
    await userEvent.click(await screen.findByLabelText('Reps for set 1'))
    await userEvent.tab()
    expect(calls.filter((c) => c.key.startsWith('POST'))).toEqual([])
  })

  it('records effort in words, stored as RPE', async () => {
    const calls = fakeApi({
      'GET /extractions/x1': card(120),
      'POST /extractions/x1/edit': reply(card(120)),
    })
    renderApp('/review/x1')
    await userEvent.click(await screen.findByRole('button', { name: 'Set 1 options' }))
    const sheet = await screen.findByRole('dialog', { name: 'Edit set' })
    await userEvent.click(within(sheet).getByRole('button', { name: /^Hard/ }))
    await userEvent.click(within(sheet).getByRole('button', { name: 'Done' }))
    await waitFor(() => expect(calls.at(-1)?.body).toEqual({ edits: [{ path: 'exercises.0.sets.0', field: 'rpe', value: 8.5 }] }))
  })

  it('takes an exact RPE from under its effort word', async () => {
    const calls = fakeApi({
      'GET /extractions/x1': card(120),
      'POST /extractions/x1/edit': reply(card(120)),
    })
    renderApp('/review/x1')
    await userEvent.click(await screen.findByRole('button', { name: 'Set 1 options' }))
    const sheet = await screen.findByRole('dialog', { name: 'Edit set' })
    await userEvent.click(within(sheet).getByRole('button', { name: 'RPE 9' }))
    // 9 is a Hard effort: the word lights up too.
    expect(within(sheet).getByRole('button', { name: /^Hard/ })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(within(sheet).getByRole('button', { name: 'Done' }))
    await waitFor(() => expect(calls.at(-1)?.body).toEqual({ edits: [{ path: 'exercises.0.sets.0', field: 'rpe', value: 9 }] }))
  })

  it('deletes a set and brings it back with Undo', async () => {
    const calls = fakeApi({
      'GET /extractions/x1': card(120),
      'POST /extractions/x1/edit': reply(card(120, false)),
    })
    renderApp('/review/x1')
    await userEvent.click(await screen.findByRole('button', { name: 'Set 1 options' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Remove set' }))

    await screen.findByText('Set removed')
    expect(calls.at(-1)?.body).toEqual({ op: { op: 'remove', path: 'exercises.0.sets.0' } })
    expect(screen.queryByLabelText('Weight for set 1')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Undo' }))
    expect(screen.getByLabelText('Weight for set 1')).toHaveValue('120')
  })

  it('confirms with the edited extract and opens the saved session', async () => {
    const calls = fakeApi({
      'GET /extractions/x1': card(120),
      'POST /extractions/x1/edit': reply(card(122.5)),
      'POST /extractions/x1/confirm': { session_id: 's9' },
      'GET /programs': [{
        id: 'p1', name: 'Strength', deload_after_days: 28, following: true, following_since: null,
        next_workout_id: 'w2',
        workouts: [
          { id: 'w1', position: 1, name: 'Bench', last_done: null, exercises: [] },
          { id: 'w2', position: 2, name: null, last_done: null, exercises: [] },
        ],
      }],
      'GET /sessions/s9': { session_id: 's9', date: '2026-10-04', program: null, focus: 'Strength', duration_minutes: null, notes: null, exercises: [] },
    })
    const location = renderApp('/review/x1')
    const weight = await screen.findByLabelText('Weight for set 1')
    await userEvent.clear(weight)
    await userEvent.type(weight, '122.5')
    await userEvent.tab()
    await waitFor(() => expect(screen.getByLabelText('Weight for set 1')).toHaveValue('122.5'))
    // The next workout is suggested; the session takes its name at Confirm.
    expect(await screen.findByRole('button', { name: /Workout 2/ })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Confirm session' }))

    await waitFor(() => expect(location.history.at(-1)).toBe('/history/s9'))
    expect(calls.filter((c) => c.key === 'POST /extractions/x1/edit').at(-1)?.body).toEqual({
      extract: { v: 'next' },
      edits: [{ path: '', field: 'focus', value: 'Workout 2' }],
    })
    expect(calls.find((c) => c.key === 'POST /extractions/x1/confirm')?.body).toEqual({
      extract: { v: 'next' },
      corrections: [{ source: 'manual' }, { source: 'manual' }],
      program_workout_id: 'w2',
    })
  })

  it('confirming a note saved before says so and links to its session', async () => {
    const calls = fakeApi({
      'GET /extractions/x1': card(120),
      'GET /programs': [],
      'POST /extractions/x1/edit': reply(card(120)),
      'POST /extractions/x1/confirm': new Response(
        JSON.stringify({ detail: 'This note is already saved.', session_id: 's9' }), { status: 409 },
      ),
    })
    const location = renderApp('/review/x1')
    await userEvent.click(await screen.findByRole('button', { name: 'Confirm session' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('This note is already saved.')
    expect(calls.filter((c) => c.key === 'POST /extractions/x1/confirm')).toHaveLength(1)
    await userEvent.click(screen.getByRole('link', { name: 'Open it' }))
    expect(location.history.at(-1)).toBe('/history/s9')
  })

  it('marks what the AI was unsure of and counts it', async () => {
    const unsure = card(120)
    unsure.session_header.uncertain_fields = ['date']
    unsure.exercises[0].working_set_rows[0].uncertain_fields = ['weight_kg']
    fakeApi({ 'GET /extractions/x1': unsure })
    renderApp('/review/x1')
    expect(await screen.findByRole('button', { name: '2 things to check' })).toBeInTheDocument()
    expect(screen.getByText(/check this/)).toBeInTheDocument()
    expect(screen.getByLabelText('Weight for set 1')).toHaveClass('border-warning')
    expect(screen.getByLabelText('Reps for set 1')).not.toHaveClass('border-warning')
  })

  it('choosing Not part of a program leaves the session out of it', async () => {
    const calls = fakeApi({
      'GET /extractions/x1': card(120),
      'POST /extractions/x1/edit': reply(card(120)),
      'POST /extractions/x1/confirm': { session_id: 's9' },
      'GET /programs': [{ id: 'p1', name: 'Strength', deload_after_days: 28, following: true, following_since: null, next_workout_id: 'w2',
        deload: { days_since: 0, due: false, in_progress: 0 },
        workouts: [{ id: 'w2', position: 2, name: null, last_done: null, exercises: [], warmup: [], cooldown: [] }] }],
      'GET /sessions/s9': { session_id: 's9', date: '2026-10-04', program: null, focus: null, duration_minutes: null, notes: null, exercises: [] },
    })
    renderApp('/review/x1')
    await userEvent.click(await screen.findByRole('button', { name: /Workout 2/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'Not part of a program' }))
    expect(await screen.findByRole('button', { name: /^Workout\s*Not part of a program/ })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Confirm session' }))
    await waitFor(() => expect(calls.some((c) => c.key === 'POST /extractions/x1/confirm')).toBe(true))
    const body = calls.find((c) => c.key === 'POST /extractions/x1/confirm')!.body as { program_workout_id?: string }
    expect(body.program_workout_id).toBeUndefined()
  })

  it('says in the fix box why a fix failed, and keeps the message', async () => {
    // No fake for /correct, so it fails; the server's plain reason is shown in the box.
    fakeApi({ 'GET /extractions/x1': card(120) })
    renderApp('/review/x1')
    const box = await screen.findByLabelText('What to change')
    await userEvent.type(box, 'Add two warm-up sets')
    await userEvent.click(screen.getByRole('button', { name: 'Fix it' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent("Couldn't make that fix, so nothing changed.")
    expect(alert).toHaveTextContent('no fake for POST /extractions/x1/correct')
    expect(box).toHaveValue('Add two warm-up sets')

    await userEvent.type(box, ' at 40 kg')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('adds a warmup set from the exercise menu and opens it', async () => {
    const withWarmup = card(120)
    withWarmup.exercises[0].warmup_rows.push({ number: 2, weight_kg: 80, rep_count: null, notes: null, uncertain_fields: [], path: 'exercises.0.warmup_sets.1' })
    fakeApi({
      'GET /extractions/x1': card(120),
      'POST /extractions/x1/edit': { ...reply(withWarmup), created_path: 'exercises.0.warmup_sets.1' },
    })
    renderApp('/review/x1')
    await userEvent.click(await screen.findByRole('button', { name: 'Options for Squat' }))
    await userEvent.click(screen.getByRole('button', { name: 'Add warm-up set' }))
    const sheet = await screen.findByRole('dialog', { name: 'Edit set' })
    expect(sheet).toHaveTextContent('Squat')
    expect(within(sheet).getByRole('button', { name: 'Warm-up' })).toHaveAttribute('aria-pressed', 'true')
  })
})
