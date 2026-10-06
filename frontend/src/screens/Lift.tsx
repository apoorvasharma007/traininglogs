import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import LineChart from '@/components/LineChart'
import { LoadError, Loading } from '@/components/QueryStatus'
import ScreenHeader from '@/components/ScreenHeader'
import { api } from '@/lib/api'
import { dayLabel, shortDate } from '@/lib/format'
import { inRange, liftValue, setText } from '@/lib/lifts'
import type { LiftDetail, LiftPoint } from '@/lib/types'

const RANGES = [
  { label: '4 weeks', days: 28 },
  { label: '12 weeks', days: 84 },
  { label: 'All', days: null },
] as const

export default function Lift({ params }: { params: { name: string } }) {
  const name = decodeURIComponent(params.name)
  const [range, setRange] = useState<number | null>(84)
  const lift = useQuery({
    queryKey: ['lift', name],
    queryFn: () => api<LiftDetail>(`/progress/lifts/${encodeURIComponent(name)}`),
  })

  const counted = (lift.data?.points ?? []).filter((p): p is LiftPoint & { value: number } => p.value != null)
  const latest = counted[counted.length - 1]
  // Sessions with no RPE have no estimate; a weighted lift plots their heaviest weight instead.
  // A bodyweight lift doesn't, since its line is reps.
  const plotted = (lift.data?.points ?? []).filter(
    (p) => p.value != null || (lift.data?.measure !== 'bodyweight_reps' && p.heaviest_kg != null),
  )
  const shown = inRange(plotted, range)
  const hasHollow = shown.some((p) => p.value == null)
  // The range buttons only change anything once the history goes back more than 4 weeks.
  const longHistory = inRange(plotted, 28).length < plotted.length

  return (
    <div>
      <ScreenHeader back="/progress" backLabel="Back to Progress" title={name} />
      {lift.isPending && <Loading />}
      {lift.isError && <LoadError error={lift.error} retry={() => lift.refetch()} />}
      {lift.data && plotted.length === 0 && <p className="px-1 text-sm text-muted-foreground">Not logged yet</p>}
      {lift.data && plotted.length > 0 && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1 px-1">
            <span className="text-[13px] text-muted-foreground">
              {lift.data.measure === 'bodyweight_reps' ? 'Reps at bodyweight' : 'Estimated max'}
            </span>
            {latest ? (
              <span className="flex items-baseline gap-2.5">
                <span className="font-mono text-[40px] font-semibold tracking-tight">{liftValue(lift.data, latest.value)}</span>
                {latest.records.length > 0 && (
                  <span className="rounded-full bg-highlight-soft px-2 py-0.5 text-xs font-semibold text-highlight">Record</span>
                )}
              </span>
            ) : (
              <>
                <span className="font-mono text-[40px] font-semibold tracking-tight">—</span>
                <span className="text-[13px] text-muted-foreground">No sets with an RPE yet</span>
              </>
            )}
          </div>

          {longHistory && (
            <div role="group" aria-label="Time range" className="grid grid-cols-3 rounded-xl bg-border/60 p-0.5">
              {RANGES.map((r) => (
                <button
                  key={r.label}
                  type="button"
                  aria-pressed={range === r.days}
                  onClick={() => setRange(r.days)}
                  className={`h-9 rounded-[10px] text-[13px] font-semibold ${
                    range === r.days ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground'
                  }`}
                >
                  {r.label}
                </button>
              ))}
            </div>
          )}

          <div className="rounded-2xl border border-border bg-card px-2 pt-3 pb-2">
            <LineChart
              label={`${name} by session`}
              points={shown.map((p) => ({
                value: p.value ?? p.heaviest_kg!,
                tick: shortDate(p.date),
                record: p.value != null && p.records.length > 0,
                hollow: p.value == null,
              }))}
              format={(v) => liftValue(lift.data, v)}
              hollowLabel="heaviest"
            />
            {lift.data.measure !== 'bodyweight_reps' && (
              <p className="px-2 pt-1 text-xs text-muted-foreground">
                Estimated from sets with an RPE.{hasHollow && ' ○ Heaviest weight, for sessions with no RPE.'}
              </p>
            )}
          </div>

          <section>
            <h2 className="mb-2 px-1 text-[15px] font-semibold">Sessions</h2>
            <div className="grid grid-cols-[76px_minmax(0,1fr)_40px_auto] gap-2.5 px-1 pb-1 text-[11px] font-semibold tracking-wide text-faint-foreground">
              <span>DATE</span>
              <span>SET</span>
              <span>RPE</span>
            </div>
            <ul>
              {[...shown].reverse().map((p) => (
                <li
                  key={p.session_id}
                  className="grid min-h-12 grid-cols-[76px_minmax(0,1fr)_40px_auto] items-center gap-2.5 border-t border-border px-1"
                >
                  <span className="font-mono text-xs text-muted-foreground">{dayLabel(p.date)}</span>
                  <span className="font-mono text-sm">{setText(p.best_set)}</span>
                  <span className="font-mono text-sm text-muted-foreground">{p.best_set.rpe ?? ''}</span>
                  <span className="text-[11px] font-semibold text-highlight">{p.records.length > 0 && 'Record'}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </div>
  )
}
