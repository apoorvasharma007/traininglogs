import { useQuery } from '@tanstack/react-query'
import { ChevronRight } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'wouter'
import PageTitle from '@/components/PageTitle'
import { LoadError, Loading } from '@/components/QueryStatus'
import { api } from '@/lib/api'
import { dayLabel, groupByWeek, sessionName } from '@/lib/format'
import type { SessionSummary } from '@/lib/types'

export default function History() {
  const [today] = useState(() => new Date())
  // Newest first, as the API returns them.
  const sessions = useQuery({
    queryKey: ['sessions'],
    queryFn: () => api<SessionSummary[]>('/sessions?limit=500'),
  })

  return (
    <div className="flex flex-col gap-5">
      <PageTitle sub={sessions.data && `${sessions.data.length} sessions`}>History</PageTitle>
      {sessions.isPending && <Loading />}
      {sessions.isError && <LoadError error={sessions.error} retry={() => sessions.refetch()} />}
      {sessions.data?.length === 0 && (
        <p className="px-1 text-sm text-muted-foreground">No sessions yet. Log one from the Train tab.</p>
      )}
      {sessions.data &&
        groupByWeek(sessions.data, (s) => s.date, today).map((week) => (
          <section key={week.title} className="flex flex-col gap-2">
            <h2 className="px-1 text-sm font-semibold">{week.title}</h2>
            <div className="overflow-hidden rounded-2xl border border-border bg-card">
              {week.items.map((s) => (
                <Link
                  key={s.session_id}
                  href={`/history/${encodeURIComponent(s.session_id)}`}
                  className="grid min-h-15 grid-cols-[66px_minmax(0,1fr)_18px] items-center gap-2.5 border-t border-border px-3.5 py-2 first:border-t-0"
                >
                  <span className="font-mono text-xs text-muted-foreground">{dayLabel(s.date)}</span>
                  <span className="flex min-w-0 flex-col gap-0.5">
                    <span className="text-sm font-semibold">{sessionName(s)}</span>
                    <span className="truncate text-xs text-muted-foreground">{s.exercises.join(' · ')}</span>
                  </span>
                  <ChevronRight size={16} aria-hidden className="text-faint-foreground" />
                </Link>
              ))}
            </div>
          </section>
        ))}
    </div>
  )
}
