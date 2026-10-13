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
    // It asks first.
    await userEvent.click(within(await screen.findByRole('dialog', { name: 'Remove Bench Press?' })).getByRole('button', { name: 'Remove' }))
    await waitFor(() => expect(calls.at(-1)).toEqual({ key: 'PUT /me/key-lifts', body: { names: ['Squat'] } }))
    expect(screen.queryByRole('button', { name: 'Remove Bench Press' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '+ Add Lift' }))
    await userEvent.click(within(await screen.findByRole('dialog', { name: 'Add a Key Lift' })).getByRole('button', { name: 'Leg Extension' }))
    await waitFor(() => expect(calls.at(-1)).toEqual({ key: 'PUT /me/key-lifts', body: { names: ['Squat', 'Leg Extension'] } }))
  })

  it('sends feedback: pick the kind, type it, Send, and it says thank you', async () => {
    const calls = fakeApi({
      'GET /progress/lifts': { key_lifts: [], other_lifts: [] }, 'GET /me/ai-usage': { total_usd: 0 },
      'POST /feedback': { id: 'f1' },
    })
    renderApp('/settings')
    await userEvent.click(await screen.findByRole('button', { name: /Send Feedback/ }))
    const sheet = await screen.findByRole('dialog', { name: 'Send Feedback' })
    expect(within(sheet).getByRole('button', { name: 'Send' })).toBeDisabled()
    await userEvent.click(within(sheet).getByRole('button', { name: 'Problem' }))
    await userEvent.type(within(sheet).getByLabelText('Message'), 'The timer froze')
    await userEvent.click(within(sheet).getByRole('button', { name: 'Send' }))
    expect(await within(sheet).findByText('Sent. Thank You.')).toBeInTheDocument()
    expect(calls.at(-1)).toEqual({ key: 'POST /feedback', body: { kind: 'bug', message: 'The timer froze' } })
  })

  it('Export as CSV downloads the file the server names', async () => {
    fakeApi({ 'GET /progress/lifts': { key_lifts: [], other_lifts: [] }, 'GET /me/ai-usage': { total_usd: 0 } })
    const fake = globalThis.fetch
    let asked = ''
    globalThis.fetch = ((url: string, init?: RequestInit) => {
      if (!String(url).startsWith('/me/export')) return fake(url, init)
      asked = String(url)
      return Promise.resolve(new Response('date,session\n', {
        status: 200, headers: { 'Content-Disposition': 'attachment; filename="traininglogs-2026-10-11.csv"' },
      }))
    }) as typeof fetch
    URL.createObjectURL = () => 'blob:export'
    URL.revokeObjectURL = () => {}
    const saved: string[] = []
    HTMLAnchorElement.prototype.click = function () { saved.push(this.download) }
    renderApp('/settings')
    await userEvent.click(await screen.findByRole('button', { name: 'Export as CSV' }))
    await waitFor(() => expect(saved).toEqual(['traininglogs-2026-10-11.csv']))
    expect(asked).toBe('/me/export?format=csv')
  })
})
