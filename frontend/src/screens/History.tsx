import { useQuery } from '@tanstack/react-query'
import { ChevronRight } from 'lucide-react'
import { Chevron, Collapse } from '@/components/Collapse'
import { useState } from 'react'
import { Link } from 'wouter'
import PageTitle from '@/components/PageTitle'
import { LoadError, Loading } from '@/components/QueryStatus'
import { api } from '@/lib/api'
import { dayLabel, groupByWeek, historyName, splitByMonth } from '@/lib/format'
import type { SessionSummary } from '@/lib/types'

/** The last 30 days by week, open; older sessions folded into one row per month. */
export default function History() {
  const [today] = useState(() => new Date())
  const [open, setOpen] = useState<Set<string>>(new Set())
  // Newest first, as the API returns them.
  const sessions = useQuery({
    queryKey: ['sessions'],
    queryFn: () => api<SessionSummary[]>('/sessions?limit=500'),
  })
  const { recent, months } = splitByMonth(sessions.data ?? [], (s) => s.date, today)

  function toggle(month: string) {
    const next = new Set(open)
    if (!next.delete(month)) next.add(month)
    setOpen(next)
  }

  return (
    <div className="flex flex-col gap-5">
      <PageTitle sub={sessions.data && `${sessions.data.length} sessions`}>History</PageTitle>
      {sessions.isPending && <Loading />}
      {sessions.isError && <LoadError error={sessions.error} retry={() => sessions.refetch()} />}
      {sessions.data?.length === 0 && (
        <p className="px-1 text-sm text-muted-foreground">No sessions yet. Log one from the Train tab.</p>
      )}
      {groupByWeek(recent, (s) => s.date, today).map((week) => (
        <section key={week.title} className="flex flex-col gap-2">
          <h2 className="px-1 text-sm font-semibold">{week.title}</h2>
          <Rows sessions={week.items} />
        </section>
      ))}
      {months.length > 0 && (
        <div className="flex flex-col gap-2">
          {months.map((m) => (
            <section key={m.title} className="flex flex-col gap-2">
              <button type="button" aria-expanded={open.has(m.title)} onClick={() => toggle(m.title)}
                className="flex min-h-13 items-center justify-between gap-3 rounded-2xl border border-border bg-card px-4 text-left transition active:scale-[0.98]">
                <span className="text-[15px] font-semibold">{m.title}</span>
                <span className="flex items-center gap-2 text-sm text-muted-foreground">
                  {m.items.length} {m.items.length === 1 ? 'session' : 'sessions'}
                  <Chevron open={open.has(m.title)} />
                </span>
              </button>
              <Collapse open={open.has(m.title)}>
                <Rows sessions={m.items} />
              </Collapse>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}

function Rows({ sessions }: { sessions: SessionSummary[] }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-border bg-card">
      {sessions.map((s) => {
        const { name, kind } = historyName(s)
        return (
          <Link
            key={s.session_id}
            href={`/history/${encodeURIComponent(s.session_id)}`}
            className="grid min-h-15 grid-cols-[66px_minmax(0,1fr)_18px] items-center gap-2.5 border-t border-border px-3.5 py-2 first:border-t-0 active:bg-muted"
          >
            <span className="font-mono text-xs text-muted-foreground">{dayLabel(s.date)}</span>
            <span className="flex min-w-0 flex-col gap-0.5">
              <span className="truncate text-sm font-semibold">{name}</span>
              <span className="truncate text-xs text-muted-foreground">{kind}</span>
            </span>
            <ChevronRight size={16} aria-hidden className="text-faint-foreground" />
          </Link>
        )
      })}
    </div>
  )
}
