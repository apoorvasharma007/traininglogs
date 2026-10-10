import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useLocation } from 'wouter'
import { LoadError, Loading } from '@/components/QueryStatus'
import ScreenHeader from '@/components/ScreenHeader'
import { api } from '@/lib/api'
import { dayLabel, historyName, kg, repsText } from '@/lib/format'
import { startSession } from '@/lib/startSession'
import type { SessionDetail } from '@/lib/types'
import ColumnHead from '@/components/ColumnHead'
import { BTN } from '@/lib/ui'

function weightText(w: number | null): string {
  return w ? kg(w) : 'BW'
}

/** A past session, read-only. */
export default function SessionView({ params }: { params: { id: string } }) {
  const id = decodeURIComponent(params.id)
  const [, navigate] = useLocation()
  const [starting, setStarting] = useState(false)
  const session = useQuery({
    queryKey: ['session', id],
    queryFn: () => api<SessionDetail>(`/sessions/${encodeURIComponent(id)}`),
  })
  const s = session.data
  const title = s && historyName(s)

  return (
    <div>
      <ScreenHeader back="/history" backLabel="Back to History" title={s ? dayLabel(s.date) : 'Session'} />
      {session.isPending && <Loading />}
      {session.isError && <LoadError error={session.error} retry={() => session.refetch()} />}
      {s && (
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1 px-1">
            <span className="text-xl font-bold tracking-tight">{title?.name}</span>
            {title?.kind && <span className="text-[15px] text-muted-foreground">{title.kind}</span>}
            {s.notes && <p className="text-[15px] text-muted-foreground">{s.notes}</p>}
          </div>
          {s.exercises.length > 0 && (
            <button type="button" disabled={starting}
              onClick={() => { setStarting(true); startSession({ past: s }).then(() => navigate('/session'), () => setStarting(false)) }}
              className={BTN.primary}>
              {starting ? 'Starting…' : 'Repeat'}
            </button>
          )}
          {s.exercises.map((ex) => (
            <section key={ex.number} className="overflow-hidden rounded-2xl border border-border bg-card">
              <div className="flex flex-col gap-1 px-4 pt-3 pb-2">
                <h2 className="text-base font-semibold">{ex.name}</h2>
                {ex.notes && <p className="text-[13px] text-muted-foreground">{ex.notes}</p>}
              </div>
              <ColumnHead className={`${COLUMNS} gap-0 px-4`}>
                <span>SET</span>
                <span>KG</span>
                <span>REPS</span>
                <span>RPE</span>
              </ColumnHead>
              {ex.warmup_sets.map((w) => (
                <Row key={`w${w.number}`} label="W" warmup weight={weightText(w.weight_kg)} reps={w.rep_count?.toString() ?? '–'} note={w.notes} />
              ))}
              {ex.sets.map((w) => (
                <Row
                  key={w.number}
                  label={String(w.number)}
                  weight={weightText(w.weight_kg)}
                  reps={repsText(w)}
                  rpe={w.rpe}
                  note={w.notes}
                />
              ))}
            </section>
          ))}
        </div>
      )}
    </div>
  )
}

const COLUMNS = 'grid grid-cols-[34px_70px_60px_minmax(0,1fr)]'

/** One set; its note, when it has one, on its own line under it, so nothing is cut off. */
function Row(props: { label: string; warmup?: boolean; weight: string; reps: string; rpe?: number | null; note: string | null }) {
  return (
    <div className="flex min-h-11 flex-col justify-center px-4 py-1.5">
      <div className={`${COLUMNS} items-center`}>
        <span className={`font-mono text-[13px] font-semibold ${props.warmup ? 'text-warning' : 'text-muted-foreground'}`}>
          {props.label}
        </span>
        <span className="font-mono text-[15px]">{props.weight}</span>
        <span className="font-mono text-[15px]">{props.reps}</span>
        <span className="font-mono text-[15px] text-muted-foreground">{props.rpe ?? ''}</span>
      </div>
      {props.note && <p className="pl-[34px] text-[13px] leading-snug text-muted-foreground">{props.note}</p>}
    </div>
  )
}
