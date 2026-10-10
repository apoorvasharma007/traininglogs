import { useQuery } from '@tanstack/react-query'
import { ArrowDownRight, ArrowRight, ArrowUpRight } from 'lucide-react'
import { Chevron, Collapse } from '@/components/Collapse'
import { useState } from 'react'
import { Link } from 'wouter'
import PageTitle from '@/components/PageTitle'
import { LoadError, Loading } from '@/components/QueryStatus'
import { api } from '@/lib/api'
import { liftValue } from '@/lib/lifts'
import type { LiftSummary, LiftsOut } from '@/lib/types'

const TREND = { up: ArrowUpRight, flat: ArrowRight, down: ArrowDownRight }

function LiftTile({ lift }: { lift: LiftSummary }) {
  const Trend = lift.trend ? TREND[lift.trend] : null
  return (
    <Link
      href={`/progress/${encodeURIComponent(lift.name)}`}
      className="flex min-h-32 flex-col gap-1.5 rounded-2xl border border-border bg-card p-3.5 transition active:scale-[0.98]"
    >
      <span className="text-sm font-semibold">{lift.name}</span>
      {lift.latest == null ? (
        <span className="flex flex-col text-[13px] leading-snug text-muted-foreground">
          {lift.sessions === 0 ? (
            'Not logged yet'
          ) : (
            <>
              <span>{lift.measure === 'bodyweight_reps' ? 'No bodyweight sets yet' : 'No sets with an RPE yet'}</span>
              <span>{lift.sessions} {lift.sessions === 1 ? 'session' : 'sessions'}</span>
            </>
          )}
        </span>
      ) : (
        <>
          <span className="flex items-center gap-1.5 font-mono text-[22px] font-semibold tracking-tight">
            {liftValue(lift, lift.latest)}
            {Trend && <Trend size={18} aria-label={`trend ${lift.trend}`} className="text-muted-foreground" />}
          </span>
          <span className="flex flex-col text-xs text-muted-foreground">
            {lift.best != null && <span>best {liftValue(lift, lift.best)}</span>}
            <span>{lift.sessions} {lift.sessions === 1 ? 'session' : 'sessions'}</span>
          </span>
        </>
      )}
    </Link>
  )
}

export default function Progress() {
  const lifts = useQuery({ queryKey: ['lifts'], queryFn: () => api<LiftsOut>('/progress/lifts') })
  const [showOthers, setShowOthers] = useState(false)

  return (
    <div className="flex flex-col gap-4">
      <PageTitle sub="Estimated max per lift, from your sets and RPE">Progress</PageTitle>
      {lifts.isPending && <Loading />}
      {lifts.isError && <LoadError error={lifts.error} retry={() => lifts.refetch()} />}
      {lifts.data && (
        <>
          <div className="grid grid-cols-2 gap-2.5">
            {lifts.data.key_lifts.map((l) => (
              <LiftTile key={l.name} lift={l} />
            ))}
          </div>
          {lifts.data.other_lifts.length > 0 && (
            <section className="overflow-hidden rounded-2xl border border-border bg-card">
              <button
                type="button"
                aria-expanded={showOthers}
                onClick={() => setShowOthers(!showOthers)}
                className="flex min-h-13 w-full items-center justify-between px-4 font-semibold active:bg-muted"
              >
                <span className="flex flex-1 items-center justify-between pr-2">
                  Other lifts <span className="font-normal text-muted-foreground">{lifts.data.other_lifts.length}</span>
                </span>
                <Chevron open={showOthers} size={18} className="text-muted-foreground" />
              </button>
              <Collapse open={showOthers}>
                {lifts.data.other_lifts.map((l) => (
                  <Link
                    key={l.name}
                    href={`/progress/${encodeURIComponent(l.name)}`}
                    className="flex min-h-12 items-center justify-between border-t border-border px-4 text-[15px] active:bg-muted"
                  >
                    <span>{l.name}</span>
                    <span className="font-mono text-[13px] text-muted-foreground">
                      {l.latest != null ? liftValue(l, l.latest) : '–'}
                    </span>
                  </Link>
                ))}
              </Collapse>
            </section>
          )}
        </>
      )}
    </div>
  )
}
