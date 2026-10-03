import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { fakeApi, renderApp as renderAt } from './test-utils'

describe('App', () => {
  fakeApi({})

  it('opens on Train with all five tabs', () => {
    renderAt('/')
    expect(screen.getByRole('heading', { name: 'Train' })).toBeInTheDocument()
    const tabs = screen.getByRole('navigation', { name: 'Main' })
    for (const label of ['Train', 'Programs', 'Progress', 'History', 'Settings']) {
      expect(tabs).toHaveTextContent(label)
    }
    expect(screen.getByRole('link', { name: 'Train' })).toHaveAttribute('aria-current', 'page')
  })

  it('switches screen when a tab is tapped', async () => {
    renderAt('/')
    await userEvent.click(screen.getByRole('link', { name: 'History' }))
    expect(screen.getByRole('heading', { name: 'History' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'History' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Train' })).not.toHaveAttribute('aria-current')
  })

  it('shows Train for an unknown address', () => {
    renderAt('/nowhere')
    expect(screen.getByRole('heading', { name: 'Train' })).toBeInTheDocument()
  })
})
