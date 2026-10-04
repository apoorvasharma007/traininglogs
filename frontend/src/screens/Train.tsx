import { useQuery } from '@tanstack/react-query'
import { ChevronRight, CloudOff } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'wouter'
import { LoadError, Loading } from '@/components/QueryStatus'
import { api } from '@/lib/api'
import { acknowledgeDeload, showDeloadReminder } from '@/lib/deload'
import { dayLabel, sessionName } from '@/lib/format'
import { usePrograms, workoutTitle } from '@/lib/programs'
import { counts, type LiveSession } from '@/lib/session'
import { startSession } from '@/lib/startSession'
import { flush, loadSession, useOutbox } from '@/lib/store'
import type { SessionDetail, SessionSummary } from '@/lib/types'

const DATE = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })
const TIME = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit' })
// The next-workout card lists this many exercises, then "+N more", so the rest stays in view.
const SHOWN = 5

/** Home: what to train next, how to log a session written down, and the less common ways in. */
export default function Train() {
  const [, navigate] = useLocation()
  const [today] = useState(() => new Date())
  const programs = usePrograms()
  const outbox = useOutbox()
  const [current, setCurrent] = useState<LiveSession | null | undefined>(undefined)
  const [, redraw] = useState(0)
  useEffect(() => {
    loadSession().then(setCurrent)
  }, [])

  const followed = programs.data?.find((p) => p.following)
  const next = followed?.workouts.find((w) => w.id === followed.next_workout_id)
  const recent = useQuery({
    queryKey: ['sessions', 'recent'],
    queryFn: () => api<SessionSummary[]>('/sessions?limit=3'),
    enabled: programs.isSuccess && !followed,
  })

  async function again(id: string) {
    const past = await api<SessionDetail>(`/sessions/${encodeURIComponent(id)}`)
    await startSession({ past })
    navigate('/session')
  }

  return (
    <div className="flex flex-col gap-3.5">
      <div className="flex flex-col gap-1 px-1 pt-12">
        <span className="text-[13px] font-medium text-muted-foreground">{DATE.format(today)}</span>
        <h1 className="text-[28px] font-bold tracking-tight">Train</h1>
      </div>

      {outbox.pending.length > 0 && (
        <div role="status" className="flex min-h-11 items-center gap-2 rounded-2xl border border-border bg-card py-1 pr-1.5 pl-3.5 text-[13px]">
          <CloudOff size={16} aria-hidden className="shrink-0 text-muted-foreground" />
          <span className="flex-1">
            <span className="font-semibold">
              {outbox.pending.length} {outbox.pending.length === 1 ? 'session' : 'sessions'} waiting to send
            </span>{' '}
            <span className="text-muted-foreground">· saved on this phone</span>
          </span>
          <button type="button" disabled={outbox.sending} onClick={() => flush()} className="h-9 px-2.5 font-semibold">
            {outbox.sending ? 'Sending…' : 'Send now'}
          </button>
        </div>
      )}

      {followed && showDeloadReminder(followed, today) && (
        <div role="status" className="flex min-h-11 items-center gap-1 rounded-xl border border-warning/40 bg-warning-soft py-0.5 pr-0.5 pl-3.5 text-[13px] text-warning">
          <span className="flex-1">
            <span className="font-semibold">Deload due</span> · {Math.round(followed.deload.days_since / 7)} weeks of training
          </span>
          <button type="button" onClick={() => { acknowledgeDeload(followed, today); redraw((n) => n + 1) }} className="h-10 px-3 font-bold">
            OK
          </button>
        </div>
      )}

      {current ? (
        <Link href="/session" className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4">
          <span className="flex flex-col gap-1">
            <span className="text-xs font-semibold text-highlight">Session in progress</span>
            <span className="text-[22px] font-bold tracking-tight">{current.title}</span>
            <span className="text-[13px] text-muted-foreground">
              Started {TIME.format(new Date(current.startedAt))} · {counts(current).done} of {counts(current).total} sets done ·
              saved on this phone
            </span>
          </span>
          <span className="flex h-13 items-center justify-center rounded-2xl bg-primary font-semibold text-primary-foreground">Resume</span>
        </Link>
      ) : programs.isPending || current === undefined ? (
        <Loading />
      ) : programs.isError ? (
        <LoadError error={programs.error} retry={() => programs.refetch()} />
      ) : followed && next ? (
        <div className="overflow-hidden rounded-2xl border border-border bg-card">
          <Link href={`/programs/${followed.id}`} className="flex min-h-13 items-center gap-2.5 border-b border-border bg-muted px-4 active:opacity-80">
            <span className="flex-1 text-[15px] font-semibold">{followed.name}</span>
            <ChevronRight size={18} aria-hidden className="text-faint-foreground" />
          </Link>
          <div className="flex flex-col gap-3 px-4 pt-3.5 pb-4">
            {/* A summary: names only. Sets, reps and alternatives show once the workout starts. */}
            <span className="text-[22px] font-bold tracking-tight">{workoutTitle(next)}</span>
            {next.exercises.length > 0 && (
              <ul className="flex flex-col">
                {next.exercises.slice(0, SHOWN).map((e) => (
                  <li key={e.name} className="flex min-h-8.5 items-center border-t border-border text-sm">
                    <span className="truncate">{e.name}</span>
                  </li>
                ))}
                {next.exercises.length > SHOWN && (
                  <li className="flex min-h-8.5 items-center border-t border-border text-sm text-muted-foreground">
                    +{next.exercises.length - SHOWN} more
                  </li>
                )}
              </ul>
            )}
            <button type="button"
              onClick={() => startSession({ program: followed, workout: next }).then(() => navigate('/session'))}
              className="h-13 rounded-2xl bg-primary font-semibold text-primary-foreground transition active:scale-[0.98]">
              Start workout
            </button>
          </div>
        </div>
      ) : followed ? (
        <div className="flex flex-col gap-2 rounded-2xl border border-dashed border-border p-5 text-sm">
          <p className="font-semibold">{followed.name} has no workouts yet</p>
          <Link href={`/programs/${followed.id}`} className="font-semibold underline">
            Open the program
          </Link>
        </div>
      ) : (
        <section className="flex flex-col gap-2">
          <h2 className="px-1 text-sm font-semibold">Do a recent session again</h2>
          {recent.data && recent.data.length > 0 ? (
            <div className="overflow-hidden rounded-2xl border border-border bg-card">
              {recent.data.map((s) => (
                <div key={s.session_id} className="flex min-h-14 items-center gap-3 border-t border-border py-2 pr-2 pl-4 first:border-t-0">
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate text-[15px] font-semibold">{sessionName(s)}</span>
                    <span className="text-xs text-muted-foreground">{dayLabel(s.date)}</span>
                  </span>
                  <button type="button" onClick={() => again(s.session_id)}
                    className="h-10 shrink-0 rounded-xl border border-border px-3 text-[13px] font-semibold">
                    Do again
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="px-1 text-sm text-muted-foreground">Your sessions will show here.</p>
          )}
          <Link href="/programs" className="self-start px-1 text-[13px] font-semibold text-muted-foreground underline underline-offset-2">
            Or follow a program
          </Link>
        </section>
      )}

      <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4">
        <div className="flex flex-col gap-1">
          <span className="text-[15px] font-semibold">Wrote it down instead?</span>
          <span className="text-[13px] leading-snug text-muted-foreground">
            Paste the notes from your phone or a notebook. The app sorts them into exercises and sets, and you check them before
            saving.
          </span>
        </div>
        <Link href="/log" className="flex h-12 items-center justify-center rounded-2xl border border-border font-semibold transition active:scale-[0.98]">
          Log from notes
        </Link>
      </div>

      <p className="flex flex-wrap justify-center gap-x-4 px-1 text-[13px] font-semibold text-muted-foreground">
        <Link href="/history" className="py-2">
          Repeat a past session
        </Link>
        <button type="button" onClick={() => startSession('blank').then(() => navigate('/session'))} className="py-2">
          Ad-hoc workout
        </button>
      </p>
    </div>
  )
}
