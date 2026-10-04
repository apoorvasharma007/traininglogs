import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { LiftDetail } from '@/lib/types'
import { fakeApi, renderApp } from '@/test-utils'

const set = (weight: number, reps: number, rpe: number | null) => ({ number: 1, weight_kg: weight, reps, rpe })

function squat(points: LiftDetail['points']): LiftDetail {
  const valued = points.filter((p) => p.value != null)
  return {
    name: 'Squat', measure: 'estimated_max', sessions: points.length, trend: null,
    latest: valued.at(-1)?.value ?? null, best: null, last_date: points.at(-1)?.date ?? null, points,
  }
}

describe('Lift', () => {
  it('estimates only from sets with an RPE, and shows other sessions at their heaviest weight', async () => {
    fakeApi({
      'GET /progress/lifts/Squat': squat([
        { session_id: 'a', date: '2026-09-28', value: 123.3, method: 'rpe', heaviest_kg: 100, records: [], best_set: set(100, 5, 8) },
        { session_id: 'b', date: '2026-10-02', value: null, method: null, heaviest_kg: 110, records: [], best_set: set(110, 3, null) },
      ]),
    })
    renderApp('/progress/Squat')
    expect((await screen.findAllByText('123.3 kg'))[0]).toBeInTheDocument()
    expect(screen.getByText(/Estimated from sets with an RPE\. ○ Heaviest weight, for sessions with no RPE\./)).toBeInTheDocument()
    expect(screen.getByText(/heaviest, no RPE/)).toHaveTextContent('110 kg heaviest, no RPE')
  })

  it('with no RPE at all, shows no estimate but still the sessions', async () => {
    fakeApi({
      'GET /progress/lifts/Squat': squat([
        { session_id: 'b', date: '2026-10-02', value: null, method: null, heaviest_kg: 110, records: [], best_set: set(110, 3, null) },
      ]),
    })
    renderApp('/progress/Squat')
    expect(await screen.findByText('No sets with an RPE yet')).toBeInTheDocument()
    expect(screen.getByText(/heaviest, no RPE/)).toBeInTheDocument()
  })
})
