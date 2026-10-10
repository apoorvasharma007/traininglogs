import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import { errorText, ShownError } from './errors'

describe('api errors', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('says there is no connection when the request never reaches the server', async () => {
    vi.stubGlobal('fetch', () => Promise.reject(new TypeError('Load failed')))
    await expect(api('/x')).rejects.toThrow('No connection. Check your internet and try again.')
  })

  it('says the server took too long when the request times out', async () => {
    vi.stubGlobal('fetch', () => Promise.reject(new DOMException('The operation timed out.', 'TimeoutError')))
    await expect(api('/x')).rejects.toThrow('The server took too long to answer. Try again.')
  })

  it('shows a plain sentence, not a status code, for a server error that gives no reason', async () => {
    vi.stubGlobal('fetch', () => Promise.resolve(new Response('Internal Server Error', { status: 500 })))
    await expect(api('/x')).rejects.toThrow('Something went wrong on our side. Try again in a minute.')
  })

  it("shows the server's own reason when it gives one", async () => {
    const body = JSON.stringify({ detail: "Couldn't reach your data. Try again in a minute." })
    vi.stubGlobal('fetch', () => Promise.resolve(new Response(body, { status: 503 })))
    await expect(api('/x')).rejects.toThrow("Couldn't reach your data. Try again in a minute.")
  })

  it("never shows FastAPI's validation list", async () => {
    const body = JSON.stringify({ detail: [{ loc: ['body', 'reps'], msg: 'Field required', type: 'missing' }] })
    vi.stubGlobal('fetch', () => Promise.resolve(new Response(body, { status: 422 })))
    await expect(api('/x')).rejects.toThrow('Something went wrong on our side. Try again in a minute.')
  })
})

describe('errorText', () => {
  it('shows messages written for people', () => {
    expect(errorText(new ShownError("This email isn't invited yet."))).toBe("This email isn't invited yet.")
  })

  it('hides anything else behind a fallback', () => {
    expect(errorText(new TypeError("undefined is not an object (evaluating 'x.sets')"))).toBe('Something went wrong. Try again.')
    expect(errorText('boom', 'Couldn’t save.')).toBe('Couldn’t save.')
  })
})
