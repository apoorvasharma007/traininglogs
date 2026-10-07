import { ChevronRight, CloudOff, NotebookPen, Plus } from 'lucide-react'
import Parts from '@/components/Parts'
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'wouter'
import { LoadError, Loading } from '@/components/QueryStatus'
import { acknowledgeDeload, showDeloadReminder } from '@/lib/deload'
import { usePrograms, workoutName } from '@/lib/programs'
import type { LiveSession } from '@/lib/session'
import { startSession } from '@/lib/startSession'
import { flush, loadSession, useOutbox } from '@/lib/store'

const DATE = new Intl.DateTimeFormat('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })
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
  useEffect(() => {
    loadSession().then(setCurrent)
  }, [])

  const followed = programs.data?.find((p) => p.following)
  const next = followed?.workouts.find((w) => w.id === followed.next_workout_id)

  return (
    <div className="flex flex-col gap-3.5">
      <div className="flex flex-col gap-1 px-1 pt-12">
        <span className="text-[13px] font-medium text-muted-foreground">{DATE.format(today)}</span>
        <h1 className="text-[28px] font-bold tracking-tight">Training Logs</h1>
      </div>

      {outbox.pending.length > 0 && (
        <div role="status" className="flex min-h-11 items-center gap-2 rounded-2xl border border-border bg-card py-1 pr-1.5 pl-3.5 text-[13px]">
          <CloudOff size={16} aria-hidden className="shrink-0 text-muted-foreground" />
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
        <Link href="/session" className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4">
          <span className="flex flex-col gap-1">
            <span className="text-xs font-semibold text-highlight">Session in Progress</span>
            <span className="text-[22px] font-bold tracking-tight">{current.title}</span>
            <Parts className="text-[13px] text-muted-foreground" items={[
              `Started ${TIME.format(new Date(current.startedAt))}`,
              'Saved on this phone',
            ]} />
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
            <span className="text-[22px] font-bold tracking-tight">{workoutName(next)}</span>
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
              Start Workout
            </button>
          </div>
        </div>
      ) : followed ? (
        <div className="flex flex-col gap-2 rounded-2xl border border-dashed border-border p-5 text-sm">
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
            <Link href="/programs/templates" className="flex h-12 items-center justify-center rounded-2xl bg-primary text-sm font-semibold text-primary-foreground transition active:scale-[0.98]">
              Browse Templates
            </Link>
            <Link href="/programs" className="flex h-12 items-center justify-center rounded-2xl border border-border text-sm font-semibold transition active:scale-[0.98]">
              Create Your Own
            </Link>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2.5">
        <button type="button" onClick={() => startSession('blank').then(() => navigate('/session'))}
          className="flex flex-col gap-2.5 rounded-2xl border border-border bg-card p-4 text-left transition active:scale-[0.98]">
          <span className="flex size-10 items-center justify-center rounded-xl bg-muted"><Plus size={22} aria-hidden /></span>
          <span className="flex flex-col gap-0.5">
            <span className="text-[15px] font-semibold">Ad-hoc Workout</span>
            <span className="text-[13px] leading-snug text-muted-foreground">Type in exercises as you go</span>
          </span>
        </button>
        <Link href="/log" className="flex flex-col gap-2.5 rounded-2xl border border-border bg-card p-4 text-left transition active:scale-[0.98]">
          <span className="flex size-10 items-center justify-center rounded-xl bg-muted"><NotebookPen size={22} aria-hidden /></span>
          <span className="flex flex-col gap-0.5">
            <span className="text-[15px] font-semibold">Wrote it down instead?</span>
            <span className="text-[13px] leading-snug text-muted-foreground">Paste, snap or say it. AI does the rest.</span>
          </span>
        </Link>
      </div>

      <Link href="/history" className="self-center py-2 text-[13px] font-semibold text-muted-foreground">
        Repeat a Past Session
      </Link>
    </div>
  )
}
