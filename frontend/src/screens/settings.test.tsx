import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { fakeApi, renderApp } from '@/test-utils'

describe('Settings', () => {
  it("shows what the person's AI use has cost so far, in dollars to the cent", async () => {
    fakeApi({ 'GET /progress/lifts': { key_lifts: [], other_lifts: [] }, 'GET /me/ai-usage': { total_usd: 0.3428 } })
    renderApp('/settings')
    expect(await screen.findByText('$0.34')).toBeInTheDocument()
    expect(screen.getByText('Total So Far')).toBeInTheDocument()
  })
})
