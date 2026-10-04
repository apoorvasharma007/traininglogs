import { ChevronRight, CloudOff, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'wouter'
import { LoadError, Loading } from '@/components/QueryStatus'
import { deloadView, snoozeDeload, startDeload } from '@/lib/deload'
import { planText, usePrograms, workoutTitle } from '@/lib/programs'
import { counts, type LiveSession } from '@/lib/session'
import { startSession } from '@/lib/startSession'
import { flush, loadSession, useOutbox } from '@/lib/store'

const DATE = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })
// The next-workout card lists this many exercises, then "+N more", so the buttons stay in view.
const SHOWN = 5
const TIME = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit' })

/** Home: the program you follow and its next workout, or a session already going. */
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
  const deload = followed ? deloadView(followed, today) : null

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
            {outbox.sending ? 'Sending…' : 'Retry'}
          </button>
        </div>
      )}

      {followed && deload?.remind && (
        <div role="status" className="flex min-h-11 items-center gap-1 rounded-xl border border-warning/40 bg-warning-soft py-0.5 pr-0.5 pl-3.5 text-[13px] text-warning">
          <span className="flex-1">
            <span className="font-semibold">Deload due</span> · {followed.deload.days_since} days of training
          </span>
          <button type="button" onClick={() => { startDeload(followed); redraw((n) => n + 1) }} className="h-10 px-2.5 font-bold">
            Start
          </button>
          <button type="button" aria-label="Remind me in 7 days" onClick={() => { snoozeDeload(followed, today); redraw((n) => n + 1) }}
            className="flex size-10 items-center justify-center">
            <X size={16} aria-hidden />
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
            <span className="flex flex-1 flex-col">
              <span className="text-[11px] font-semibold tracking-wide text-muted-foreground">CURRENT PROGRAM</span>
              <span className="text-[15px] font-semibold">{followed.name}</span>
            </span>
            <ChevronRight size={18} aria-hidden className="text-faint-foreground" />
          </Link>
          <div className="flex flex-col gap-3 px-4 pt-3.5 pb-4">
            <div className="flex flex-col gap-1">
              <span className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                Next workout
                {deload?.next != null && (
                  <span className="rounded-full border border-warning/40 bg-warning-soft px-2 py-0.5 text-[11px] text-warning">
                    Deload {deload.next} of {deload.of}
                  </span>
                )}
              </span>
              <span className="text-[22px] font-bold tracking-tight">{workoutTitle(next)}</span>
            </div>
            {next.exercises.length > 0 && (
              <ul className="flex flex-col">
                {next.exercises.slice(0, SHOWN).map((e) => (
                  <li key={e.name} className="flex min-h-8.5 items-center justify-between gap-3 border-t border-border text-sm">
                    <span className="truncate">{e.name}</span>
                    <span className="shrink-0 font-mono text-xs text-muted-foreground">{planText(e)}</span>
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
              onClick={() => startSession({ program: followed, workout: next, deload: deload?.next != null }).then(() => navigate('/session'))}
              className="h-13 rounded-2xl bg-primary font-semibold text-primary-foreground transition active:scale-[0.98]">
              Start workout
            </button>
            <Link href={`/programs/${followed.id}`} className="self-center px-2 py-1 text-[13px] font-semibold text-muted-foreground">
              Do a different workout
            </Link>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-2 rounded-2xl border border-dashed border-border p-5 text-sm">
          <p className="font-semibold">{followed ? `${followed.name} has no workouts yet` : 'No program followed'}</p>
          <p className="text-muted-foreground">
            {followed ? 'Add workouts to it and the next one shows here.' : 'Follow a program and its next workout shows here.'}
          </p>
          <Link href={followed ? `/programs/${followed.id}` : '/programs'} className="font-semibold underline">
            {followed ? 'Open the program' : 'Go to Programs'}
          </Link>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2.5">
        <button type="button" onClick={() => startSession('blank').then(() => navigate('/session'))}
          className="flex h-12 items-center justify-center rounded-2xl border border-border bg-card text-sm font-semibold transition active:scale-[0.98]">
          Blank workout
        </button>
        <Link href="/log" className="flex h-12 items-center justify-center rounded-2xl border border-border bg-card text-sm font-semibold transition active:scale-[0.98]">
          Log from notes
        </Link>
      </div>
    </div>
  )
}
