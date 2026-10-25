import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import BodyMuscles from '@/components/BodyMuscles'

describe('BodyMuscles', () => {
  it('takes a muscle off with one tap on its pill', async () => {
    const onChange = vi.fn()
    render(<BodyMuscles mode="primary" primary={['Abs', 'Vastus Muscles']} secondary={['Lats']} onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: 'Remove Abs' }))
    expect(onChange).toHaveBeenCalledWith(['Vastus Muscles'], ['Lats'])
  })

  it('shows pills only for the muscles this body marks', () => {
    render(<BodyMuscles mode="secondary" primary={['Abs']} secondary={['Lats']} onChange={() => {}} />)
    expect(screen.getByRole('button', { name: 'Remove Lats' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Remove Abs' })).toBeNull()
  })
})
