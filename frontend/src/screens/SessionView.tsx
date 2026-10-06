import { useQuery } from '@tanstack/react-query'
import { useLocation } from 'wouter'
import { LoadError, Loading } from '@/components/QueryStatus'
import ScreenHeader from '@/components/ScreenHeader'
import { api } from '@/lib/api'
import { dayLabel, kg, repsText, sessionName } from '@/lib/format'
import { startSession } from '@/lib/startSession'
import type { SessionDetail } from '@/lib/types'

function weightText(w: number | null): string {
  return w ? kg(w) : 'BW'
}

/** A past session, read-only. */
export default function SessionView({ params }: { params: { id: string } }) {
  const id = decodeURIComponent(params.id)
  const [, navigate] = useLocation()
  const session = useQuery({
    queryKey: ['session', id],
    queryFn: () => api<SessionDetail>(`/sessions/${encodeURIComponent(id)}`),
  })
  const s = session.data

  return (
    <div>
      <ScreenHeader back="/history" backLabel="Back to History" title={s ? dayLabel(s.date) : 'Session'} />
      {session.isPending && <Loading />}
      {session.isError && <LoadError error={session.error} retry={() => session.refetch()} />}
      {s && (
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1 px-1">
            <span className="text-xl font-bold tracking-tight">{sessionName(s)}</span>
            {s.notes && <p className="text-sm text-muted-foreground">{s.notes}</p>}
          </div>
          {s.exercises.length > 0 && (
            <button type="button" onClick={() => startSession({ past: s }).then(() => navigate('/session'))}
              className="h-12 rounded-2xl bg-primary font-semibold text-primary-foreground transition active:scale-[0.98]">
              Repeat
            </button>
          )}
          {s.exercises.map((ex) => (
            <section key={ex.number} className="overflow-hidden rounded-2xl border border-border bg-card">
              <div className="flex flex-col gap-1 px-4 pt-3 pb-2">
                <h2 className="text-base font-semibold">{ex.name}</h2>
                {ex.notes && <p className="text-xs text-muted-foreground">{ex.notes}</p>}
              </div>
              <div className="grid grid-cols-[34px_70px_60px_minmax(0,1fr)] px-4 pb-1 text-[11px] font-semibold tracking-wide text-faint-foreground">
                <span>SET</span>
                <span>KG</span>
                <span>REPS</span>
                <span>NOTE</span>
              </div>
              {ex.warmup_sets.map((w) => (
                <Row key={`w${w.number}`} label="W" warmup weight={weightText(w.weight_kg)} reps={w.rep_count?.toString() ?? '–'} note={w.notes} />
              ))}
              {ex.sets.map((w) => (
                <Row
                  key={w.number}
                  label={String(w.number)}
                  weight={weightText(w.weight_kg)}
                  reps={repsText(w) + (w.rpe != null ? ` @${w.rpe}` : '')}
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

function Row(props: { label: string; warmup?: boolean; weight: string; reps: string; note: string | null }) {
  return (
    <div className="grid min-h-11 grid-cols-[34px_70px_60px_minmax(0,1fr)] items-center border-t border-border px-4">
      <span className={`font-mono text-[13px] font-semibold ${props.warmup ? 'text-warning' : 'text-muted-foreground'}`}>
        {props.label}
      </span>
      <span className="font-mono text-[15px]">{props.weight}</span>
      <span className="font-mono text-[15px]">{props.reps}</span>
      <span className="truncate text-xs text-muted-foreground">{props.note}</span>
    </div>
  )
}
