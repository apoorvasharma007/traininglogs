import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Card } from '@/lib/types'
import { fakeApi, renderApp } from '@/test-utils'

function card(weight: number, withSet = true): Card {
  return {
    session_header: { date: '2026-10-04', focus: 'Strength', program: null, uncertain_fields: [], path: '' },
    warnings: [],
    exercises: [
      {
        header: { number: 1, name: 'Squat', failed: false, path: 'exercises.0' },
        warmup_rows: [{ number: 1, weight_kg: 80, rep_count: null, notes: null, path: 'exercises.0.warmup_sets.0' }],
        working_set_rows: withSet
          ? [{ number: 1, weight_kg: weight, reps: '2', rpe: null, notes: null, path: 'exercises.0.sets.0' }]
          : [],
        note_preview: null,
        failure_reason: null,
      },
    ],
  }
}

const reply = (c: Card) => ({ extract: { v: 'next' }, card: c, correction: { source: 'manual' }, created_path: null })

describe('Review', () => {
  it('edits a set in the sheet and sends only the change', async () => {
    const calls = fakeApi({
      'GET /extractions/x1': card(120),
      'POST /extractions/x1/edit': reply(card(122.5)),
    })
    renderApp('/review/x1')
    await userEvent.click(await screen.findByRole('button', { name: 'Edit set 1' }))
    const sheet = screen.getByRole('dialog', { name: 'Edit set' })
    await userEvent.click(within(sheet).getByRole('button', { name: 'Plus 2.5 kg' }))
    await userEvent.click(within(sheet).getByRole('button', { name: 'Done' }))

    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Edit set' })).not.toBeInTheDocument())
    expect(calls.at(-1)).toEqual({
      key: 'POST /extractions/x1/edit',
      body: { edits: [{ path: 'exercises.0.sets.0', field: 'weight_kg', value: 122.5 }] },
    })
    expect(screen.getByRole('button', { name: 'Edit set 1' })).toHaveTextContent('122.5')
  })

  it('deletes a set and brings it back with Undo', async () => {
    const calls = fakeApi({
      'GET /extractions/x1': card(120),
      'POST /extractions/x1/edit': reply(card(120, false)),
    })
    renderApp('/review/x1')
    await userEvent.click(await screen.findByRole('button', { name: 'Edit set 1' }))
    await userEvent.click(screen.getByRole('button', { name: 'Delete set' }))

    await screen.findByText('Removed')
    expect(calls.at(-1)?.body).toEqual({ op: { op: 'remove', path: 'exercises.0.sets.0' } })
    expect(screen.queryByRole('button', { name: 'Edit set 1' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Undo' }))
    expect(screen.getByRole('button', { name: 'Edit set 1' })).toHaveTextContent('120')
  })

  it('confirms with the edited extract and opens the saved session', async () => {
    const calls = fakeApi({
      'GET /extractions/x1': card(120),
      'POST /extractions/x1/edit': reply(card(122.5)),
      'POST /extractions/x1/confirm': { session_id: 's9' },
      'GET /sessions/s9': { session_id: 's9', date: '2026-10-04', program: null, focus: 'Strength', duration_minutes: null, notes: null, exercises: [] },
    })
    const location = renderApp('/review/x1')
    await userEvent.click(await screen.findByRole('button', { name: 'Edit set 1' }))
    await userEvent.click(screen.getByRole('button', { name: 'Plus 2.5 kg' }))
    await userEvent.click(screen.getByRole('button', { name: 'Done' }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Edit set 1' })).toHaveTextContent('122.5'))
    await userEvent.click(screen.getByRole('button', { name: 'Confirm session' }))

    await waitFor(() => expect(location.history.at(-1)).toBe('/history/s9'))
    expect(calls.find((c) => c.key === 'POST /extractions/x1/confirm')?.body).toEqual({
      extract: { v: 'next' },
      corrections: [{ source: 'manual' }],
    })
  })

  it('adds a warmup set from the exercise menu and opens it', async () => {
    const withWarmup = card(120)
    withWarmup.exercises[0].warmup_rows.push({ number: 2, weight_kg: 80, rep_count: null, notes: null, path: 'exercises.0.warmup_sets.1' })
    fakeApi({
      'GET /extractions/x1': card(120),
      'POST /extractions/x1/edit': { ...reply(withWarmup), created_path: 'exercises.0.warmup_sets.1' },
    })
    renderApp('/review/x1')
    await userEvent.click(await screen.findByRole('button', { name: 'Options for Squat' }))
    await userEvent.click(screen.getByRole('button', { name: 'Add warmup set' }))
    const sheet = await screen.findByRole('dialog', { name: 'Edit set' })
    expect(sheet).toHaveTextContent('Squat · Warmup set')
  })
})
