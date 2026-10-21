import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { fakeApi } from '@/test-utils'
import { useReviewDoc } from './useReviewDoc'

const card = { session_header: { path: '' }, warnings: [], exercises: [] }

describe('useReviewDoc', () => {
  it('sends a second change on top of the first, not on the same starting point', async () => {
    let n = 0
    const calls = fakeApi({
      'GET /extractions/x1': card,
      'POST /extractions/x1/edit': () => ({ extract: { v: ++n }, card, correction: {}, created_path: null }),
    })
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
    )
    const { result } = renderHook(() => useReviewDoc('x1'), { wrapper })
    await waitFor(() => expect(result.current.doc).not.toBeNull())

    const edit = [{ edits: [{ path: '', field: 'focus', value: 'A' }] }]
    await act(async () => {
      await Promise.all([result.current.run(edit), result.current.run(edit)])
    })

    const sent = calls.filter((c) => c.key === 'POST /extractions/x1/edit').map((c) => (c.body as { extract?: unknown }).extract)
    expect(sent).toEqual([undefined, { v: 1 }])
    expect(result.current.corrections).toHaveLength(2)
  })
})
