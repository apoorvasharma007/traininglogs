import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import ExercisePicker from '@/components/ExercisePicker'
import { fakeApi } from '@/test-utils'

function Box({ onPick }: { onPick: (name: string) => void }) {
  const [value, setValue] = useState('')
  return <ExercisePicker aria-label="Exercise name" value={value} onChange={(e) => setValue(e.target.value)} onPick={onPick} />
}

function renderBox() {
  const calls = fakeApi({
    'POST /exercises': {},
    'GET /exercises': {
      library: [{ id: '1', name: 'Romanian Deadlift (Barbell)', other_names: ['rdl'] }],
      mine: [{ id: 'a', name: 'Zercher Squat', exercise_id: null, primary_muscles: ['Vastus Muscles'] }],
    },
  })
  const onPick = vi.fn()
  render(
    <QueryClientProvider client={new QueryClient()}>
      <Box onPick={onPick} />
    </QueryClientProvider>,
  )
  return { onPick, calls }
}

describe('ExercisePicker', () => {
  it('shows nothing before typing, then matches as you type', async () => {
    const { onPick } = renderBox()
    const box = screen.getByRole('combobox', { name: 'Exercise name' })
    await userEvent.click(box)
    expect(screen.queryByRole('button')).toBeNull()
    await userEvent.type(box, 'rdl')
    expect(await screen.findByText('Matches "rdl"')).toBeInTheDocument()
    await userEvent.click(screen.getByText('Romanian Deadlift (Barbell)'))
    expect(onPick).toHaveBeenCalledWith('Romanian Deadlift (Barbell)')
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('tags custom exercises; Custom, offered only for a new name, saves one and picks it', async () => {
    const { onPick, calls } = renderBox()
    const box = screen.getByRole('combobox', { name: 'Exercise name' })
    await userEvent.type(box, 'zercher squat')
    expect(await screen.findByText('Custom')).toBeInTheDocument()
    expect(screen.queryByText('zercher squat', { selector: 'span' })).toBeNull()
    await userEvent.type(box, ' paused')
    await userEvent.click(await screen.findByText('zercher squat paused'))
    expect(screen.getByLabelText('Exercise name', { selector: '[role=dialog] input' })).toHaveValue('zercher squat paused')
    await userEvent.click(document.querySelector('[data-group="Quads"]')!) // marks both quad muscles
    await userEvent.click(screen.getByRole('button', { name: 'Rectus Femoris' })) // unticks one
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(onPick).toHaveBeenCalledWith('zercher squat paused')
    expect(calls.find((c) => c.key === 'POST /exercises')?.body).toMatchObject({
      name: 'zercher squat paused', primary_muscles: ['Vastus Muscles'], measures: ['weight', 'reps'],
    })
  })

  it('Enter picks the top result, not the typed text', async () => {
    const { onPick } = renderBox()
    const box = screen.getByRole('combobox', { name: 'Exercise name' })
    await userEvent.type(box, 'rdl')
    await screen.findByText('Matches "rdl"')
    await userEvent.keyboard('{Enter}')
    expect(onPick).toHaveBeenCalledWith('Romanian Deadlift (Barbell)')
  })

  it('Enter on a new name with no match opens the Custom Exercise sheet', async () => {
    const { onPick } = renderBox()
    const box = screen.getByRole('combobox', { name: 'Exercise name' })
    await userEvent.type(box, 'zercher squat paused')
    await screen.findByText('Custom')
    await userEvent.keyboard('{Enter}')
    expect(screen.getByLabelText('Exercise name', { selector: '[role=dialog] input' })).toHaveValue('zercher squat paused')
    expect(onPick).not.toHaveBeenCalled()
  })

  it('Save in the sheet asks for a name, then a primary muscle, before saving', async () => {
    const { onPick, calls } = renderBox()
    await userEvent.type(screen.getByRole('combobox', { name: 'Exercise name' }), 'zercher squat paused')
    await userEvent.click(await screen.findByText('Custom'))
    const nameBox = screen.getByLabelText('Exercise name', { selector: '[role=dialog] input' })
    await userEvent.clear(nameBox)
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(nameBox).toHaveFocus()
    await userEvent.type(nameBox, 'Zercher Squat Paused')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(calls.some((c) => c.key === 'POST /exercises')).toBe(false)
    expect(onPick).not.toHaveBeenCalled()
  })
})
