import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'

describe('api errors', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('says there is no connection when the request never reaches the server', async () => {
    vi.stubGlobal('fetch', () => Promise.reject(new TypeError('Load failed')))
    await expect(api('/x')).rejects.toThrow('No connection. Check your internet and try again.')
  })

  it('shows the code of a server error that gives no reason', async () => {
    vi.stubGlobal('fetch', () => Promise.resolve(new Response('Internal Server Error', { status: 500 })))
    await expect(api('/x')).rejects.toThrow('Server error (500). Try again in a minute.')
  })

  it("shows the server's own reason when it gives one", async () => {
    const body = JSON.stringify({ detail: 'Database unavailable (503). Try again in a minute.' })
    vi.stubGlobal('fetch', () => Promise.resolve(new Response(body, { status: 503 })))
    await expect(api('/x')).rejects.toThrow('Database unavailable (503). Try again in a minute.')
  })
})
