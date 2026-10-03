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
  const shown = inRange(counted, range)
  const latest = counted[counted.length - 1]

  return (
    <div>
      <ScreenHeader back="/progress" backLabel="Back to Progress" title={name} />
      {lift.isPending && <Loading />}
      {lift.isError && <LoadError error={lift.error} retry={() => lift.refetch()} />}
      {lift.data && !latest && <p className="px-1 text-sm text-muted-foreground">No countable sets yet.</p>}
      {lift.data && latest && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1 px-1">
            <span className="text-[13px] text-muted-foreground">
              {lift.data.measure === 'bodyweight_reps' ? 'Reps at bodyweight' : 'Estimated max'}
            </span>
            <span className="flex items-baseline gap-2.5">
              <span className="font-mono text-[40px] font-semibold tracking-tight">{liftValue(lift.data, latest.value)}</span>
              {latest.records.length > 0 && (
                <span className="rounded-full bg-accent-soft px-2 py-0.5 text-xs font-semibold text-accent">Record</span>
              )}
            </span>
            <span className="text-[13px] text-muted-foreground">
              From {setText(latest.best_set)} on {dayLabel(latest.date)}
            </span>
          </div>

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

          <div className="rounded-2xl border border-border bg-card px-2 pt-3 pb-2">
            <LineChart
              label={`${name} by session`}
              points={shown.map((p) => ({ value: p.value, tick: shortDate(p.date), record: p.records.length > 0 }))}
            />
            <p className="px-2 pt-1 text-xs text-muted-foreground">Without RPE, a set counts as taken to failure.</p>
          </div>

          <section>
            <h2 className="mb-2 px-1 text-[15px] font-semibold">Sessions</h2>
            <ul>
              {[...shown].reverse().map((p) => (
                <li
                  key={p.session_id}
                  className="grid min-h-12 grid-cols-[76px_minmax(0,1fr)_auto] items-center gap-2.5 border-t border-border px-1"
                >
                  <span className="font-mono text-xs text-muted-foreground">{dayLabel(p.date)}</span>
                  <span className="text-sm">
                    <span className="font-mono font-semibold">{liftValue(lift.data, p.value)}</span>{' '}
                    <span className="text-muted-foreground">from {setText(p.best_set)}</span>
                  </span>
                  {p.records.length > 0 && <span className="text-[11px] font-semibold text-accent">Record</span>}
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </div>
  )
}
