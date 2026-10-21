import { get } from 'idb-keyval'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { SessionRequest } from '@/lib/session'

const sent = vi.fn()
let ApiError: typeof import('@/lib/api').ApiError
let enqueue: typeof import('@/lib/store').enqueue
let flush: typeof import('@/lib/store').flush

const session = (id: string) => ({ client_id: id }) as SessionRequest

describe('outbox', () => {
  // The test setup already loaded the real store, so load a fresh one that sees the mocks.
  beforeEach(async () => {
    sent.mockReset()
    vi.resetModules()
    vi.doMock('@/lib/api', async (original) => ({
      ...(await original<typeof import('@/lib/api')>()),
      api: (path: string, opts: { body: SessionRequest }) => sent(path, opts.body),
    }))
    vi.doMock('@/lib/auth', () => ({ signedInEmail: () => 'a@b.c' }))
    ;({ ApiError } = await import('@/lib/api'))
    ;({ enqueue, flush } = await import('@/lib/store'))
  })

  it('sets a refused session aside and still sends the ones behind it', async () => {
    sent.mockImplementation(async (_path: string, body: SessionRequest) => {
      if (body.client_id === 'bad') throw new ApiError(422, 'No')
    })
    await enqueue(session('bad'))
    await enqueue(session('good'))
    await flush()
    expect(sent.mock.calls.map(([, body]) => body.client_id)).toEqual(['bad', 'good'])
    expect(await get('sessions-to-send:a@b.c')).toEqual([])
    expect(await get('sessions-refused:a@b.c')).toEqual([session('bad')])
  })

  it('keeps everything waiting when the server is down', async () => {
    sent.mockRejectedValue(new ApiError(503, 'Down'))
    await enqueue(session('one'))
    await enqueue(session('two'))
    await flush()
    expect(sent).toHaveBeenCalledTimes(1)
    expect(await get('sessions-to-send:a@b.c')).toEqual([session('one'), session('two')])
  })
})
