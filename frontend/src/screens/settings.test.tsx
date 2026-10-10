import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { fakeApi, renderApp } from '@/test-utils'

const lift = (name: string) => ({ name, measure: 'estimated_max', sessions: 3, latest: null, best: null, last_date: null, trend: null })

describe('Settings', () => {
  it("shows what the person's AI use has cost so far, in dollars to the cent", async () => {
    fakeApi({ 'GET /progress/lifts': { key_lifts: [], other_lifts: [] }, 'GET /me/ai-usage': { total_usd: 0.3428 } })
    renderApp('/settings')
    expect(await screen.findByText('$0.34')).toBeInTheDocument()
    expect(screen.getByText('Total So Far')).toBeInTheDocument()
  })

  it('key lifts are your own: remove one, or add one from the lifts you log', async () => {
    const calls = fakeApi({
      'GET /progress/lifts': { key_lifts: [lift('Squat'), lift('Bench Press')], other_lifts: [lift('Leg Extension')] },
      'GET /me/ai-usage': { total_usd: 0 },
      'PUT /me/key-lifts': (body: unknown) => ({
        key_lifts: (body as { names: string[] }).names.map(lift), other_lifts: [lift('Leg Extension')],
      }),
    })
    renderApp('/settings')
    await userEvent.click(await screen.findByRole('button', { name: 'Remove Bench Press' }))
    await waitFor(() => expect(calls.at(-1)).toEqual({ key: 'PUT /me/key-lifts', body: { names: ['Squat'] } }))
    expect(screen.queryByRole('button', { name: 'Remove Bench Press' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '+ Add Lift' }))
    await userEvent.click(within(await screen.findByRole('dialog', { name: 'Add a Key Lift' })).getByRole('button', { name: 'Leg Extension' }))
    await waitFor(() => expect(calls.at(-1)).toEqual({ key: 'PUT /me/key-lifts', body: { names: ['Squat', 'Leg Extension'] } }))
  })
})
