import { ChevronRight, CloudOff, NotebookPen, Plus } from 'lucide-react'
import Parts from '@/components/Parts'
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'wouter'
import { LoadError, Loading } from '@/components/QueryStatus'
import { acknowledgeDeload, showDeloadReminder } from '@/lib/deload'
import { usePrograms, workoutName } from '@/lib/programs'
import { liveTitle, type LiveSession } from '@/lib/session'
import { startSession } from '@/lib/startSession'
import { flush, loadSession, useOutbox } from '@/lib/store'
import { BTN } from '@/lib/ui'

const DATE = new Intl.DateTimeFormat('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
const TIME = new Intl.DateTimeFormat('en-US', { hour: 'numeric', minute: '2-digit' })
// The next-workout card lists this many exercises, then "+N more", so the rest stays in view.
const SHOWN = 4

/** Home: what to train next (or a program to start with), an ad-hoc workout, notes, and repeating a past session. */
export default function Train() {
  const [, navigate] = useLocation()
  const [today] = useState(() => new Date())
  const programs = usePrograms()
  const outbox = useOutbox()
  const [current, setCurrent] = useState<LiveSession | null | undefined>(undefined)
  const [, redraw] = useState(0)
  // Which start button is waiting for its session (last time's sets come from the server).
  const [starting, setStarting] = useState<'workout' | 'blank' | null>(null)
  function start(from: Parameters<typeof startSession>[0], which: 'workout' | 'blank') {
    setStarting(which)
    startSession(from).then(() => navigate('/session'), () => setStarting(null))
  }
  useEffect(() => {
    loadSession().then(setCurrent)
  }, [])

  const followed = programs.data?.find((p) => p.following)
  const next = followed?.workouts.find((w) => w.id === followed.next_workout_id)

  return (
    <div className="flex flex-col gap-3.5">
      <div className="flex items-baseline justify-between gap-3 px-1 pt-12">
        <h1 className="text-[28px] font-bold tracking-tight">Training Logs</h1>
        <span className="font-mono text-[13px] font-semibold tracking-wider text-muted-foreground uppercase">{DATE.format(today)}</span>
      </div>

      {outbox.pending.length > 0 && (
        <div role="status" className="flex min-h-11 items-center gap-2 rounded-2xl border border-border bg-card py-1 pr-1.5 pl-3.5 text-[13px]">
          <CloudOff size={18} aria-hidden className="shrink-0 text-muted-foreground" />
          <span className="flex flex-1 flex-col">
            <span className="font-semibold">
              {outbox.pending.length} {outbox.pending.length === 1 ? 'session' : 'sessions'} waiting to send
            </span>
            <span className="text-muted-foreground">Saved on this phone</span>
          </span>
          <button type="button" disabled={outbox.sending} onClick={() => flush()} className="h-9 px-2.5 font-semibold">
            {outbox.sending ? 'Sending…' : 'Send Now'}
          </button>
        </div>
      )}

      {followed && showDeloadReminder(followed, today) && (
        <div role="status" className="flex min-h-11 items-center gap-1 rounded-xl border border-warning/40 bg-warning-soft py-0.5 pr-0.5 pl-3.5 text-[13px] text-warning">
          <span className="flex flex-1 flex-col">
            <span className="font-semibold">Deload Due</span>
            <span>{Math.round(followed.deload.days_since / 7)} weeks of training</span>
          </span>
          <button type="button" onClick={() => { acknowledgeDeload(followed, today); redraw((n) => n + 1) }} className="h-10 px-3 font-bold">
            OK
          </button>
        </div>
      )}

      {current ? (
        <Link href="/session" className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 transition active:scale-[0.98]">
          <span className="flex flex-col gap-1">
            <span className="text-[13px] font-semibold text-highlight">Session in Progress</span>
            <span className="text-[22px] font-bold tracking-tight">{liveTitle(current)}</span>
            <Parts className="text-[13px] text-muted-foreground" items={[
              `Started ${TIME.format(new Date(current.startedAt))}`,
              'Saved on this phone',
            ]} />
          </span>
          <span className={`${BTN.primary} flex items-center justify-center`}>Resume</span>
        </Link>
      ) : programs.isPending || current === undefined ? (
        <Loading />
      ) : programs.isError ? (
        <LoadError error={programs.error} retry={() => programs.refetch()} />
      ) : followed && next ? (
        <div className="overflow-hidden rounded-2xl border border-border bg-card">
          <Link href={`/programs/${followed.id}`} className="flex min-h-13 items-center gap-2.5 bg-muted px-4 active:opacity-80">
            <span className="flex-1 text-[15px] font-semibold">{followed.name}</span>
            <ChevronRight size={18} aria-hidden className="text-faint-foreground" />
          </Link>
          <div className="flex flex-col gap-3 px-4 pt-3.5 pb-4">
            {/* A summary: names only. Sets, reps and alternatives show once the workout starts. */}
            <span className="text-[22px] font-bold tracking-tight">{workoutName(next)}</span>
            {next.exercises.length > 0 && (
              <ul className="flex flex-col">
                {next.exercises.slice(0, SHOWN).map((e, i) => (
                  <li key={e.name} className="grid min-h-8.5 grid-cols-[1.5rem_minmax(0,1fr)] items-center text-[15px]">
                    <span className="font-mono text-[13px] text-faint-foreground">{i + 1}</span>
                    <span className="truncate">{e.name}</span>
                  </li>
                ))}
                {next.exercises.length > SHOWN && (
                  <li className="flex min-h-8.5 items-center pl-6 text-[15px] text-muted-foreground">
                    +{next.exercises.length - SHOWN} more
                  </li>
                )}
              </ul>
            )}
            <button type="button" disabled={starting != null}
              onClick={() => start({ program: followed, workout: next }, 'workout')}
              className={BTN.primary}>
              {starting === 'workout' ? 'Starting…' : 'Start Workout'}
            </button>
          </div>
        </div>
      ) : followed ? (
        <div className="flex flex-col gap-2 rounded-2xl bg-muted p-5 text-[15px]">
          <p className="font-semibold">{followed.name} has no workouts yet</p>
          <Link href={`/programs/${followed.id}`} className="font-semibold underline">
            Open the Program
          </Link>
        </div>
      ) : (
        <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4">
          <div className="flex flex-col gap-1">
            <span className="text-[15px] font-semibold">Start with a Program</span>
            <span className="text-[13px] text-muted-foreground">Pick a ready-made one, or build your own.</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Link href="/programs/templates" className={`${BTN.primary} flex items-center justify-center`}>
              Browse Templates
            </Link>
            <Link href="/programs?new" className={`${BTN.secondary} flex items-center justify-center`}>
              Create Your Own
            </Link>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2.5">
        <button type="button" disabled={starting != null} onClick={() => start('blank', 'blank')}
          className="flex flex-col gap-2.5 rounded-2xl border border-border bg-card p-4 text-left transition active:scale-[0.98] disabled:opacity-50">
          <span className="flex size-10 items-center justify-center rounded-xl bg-muted"><Plus size={22} aria-hidden /></span>
          <span className="flex flex-col gap-0.5">
            <span className="text-[15px] font-semibold">{starting === 'blank' ? 'Starting…' : 'Ad-hoc Workout'}</span>
            <span className="text-[13px] leading-snug text-muted-foreground">Type in exercises as you go</span>
          </span>
        </button>
        <Link href="/log" className="flex flex-col gap-2.5 rounded-2xl border border-border bg-card p-4 text-left transition active:scale-[0.98]">
          <span className="flex size-10 items-center justify-center rounded-xl bg-muted"><NotebookPen size={22} aria-hidden /></span>
          <span className="flex flex-col gap-0.5">
            <span className="text-[15px] font-semibold">Wrote It Down Instead?</span>
            <span className="text-[13px] leading-snug text-muted-foreground">Paste, snap or say it. AI does the rest.</span>
          </span>
        </Link>
      </div>

      <Link href="/history" className="self-center py-2 text-[13px] font-semibold text-muted-foreground active:opacity-60">
        Repeat a Past Session
      </Link>
    </div>
  )
}
