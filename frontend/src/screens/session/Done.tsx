import { Check } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'wouter'
import { planText, useProgram, useProgramChange, workoutTitle } from '@/lib/programs'
import { useOutbox } from '@/lib/store'
import { getLastFinished, type Finished } from '@/screens/session/finished'

/** After Finish: whether the session reached the server, an offer to update the workout, next time. */
export default function Done() {
  const [finished] = useState(getLastFinished)
  const outbox = useOutbox()
  if (!finished) {
    return (
      <div className="flex flex-col gap-3 pt-16 text-center">
        <p className="font-semibold">Nothing just finished</p>
        <Link href="/" className="font-semibold text-muted-foreground underline">
          Back to Train
        </Link>
      </div>
    )
  }
  const waiting = outbox.pending.some((r) => r.client_id === finished.clientId)

  return (
    <div className="flex min-h-dvh flex-col gap-4 pt-16 pb-8">
      <div className="flex flex-col gap-1.5 px-1">
        <span className="flex size-11 items-center justify-center rounded-full bg-highlight text-background">
          <Check size={22} strokeWidth={2.6} aria-hidden />
        </span>
        <h1 className="mt-2 text-[28px] font-bold tracking-tight">Session done</h1>
        <p className="text-sm text-muted-foreground">
          {finished.title} · {finished.minutes} min · {finished.sets} sets
        </p>
      </div>

      <div role="status" className="rounded-2xl border border-border bg-card px-4 py-3 text-sm">
        {waiting ? (
          outbox.sending ? (
            'Sending…'
          ) : (
            <>
              <p className="font-semibold">Waiting to send</p>
              <p className="text-muted-foreground">It's saved on this phone and sends by itself when you're back online.</p>
            </>
          )
        ) : (
          'Saved to your history.'
        )}
      </div>

      {finished.programId && <ProgramCards finished={finished} programId={finished.programId} />}

      <div className="flex-1" />
      <Link href="/" className="flex h-13 items-center justify-center rounded-2xl bg-primary font-semibold text-primary-foreground">
        Done
      </Link>
    </div>
  )
}

function ProgramCards({ finished, programId }: { finished: Finished; programId: string }) {
  const program = useProgram(programId)
  const change = useProgramChange(programId)
  const [answered, setAnswered] = useState(false)
  const p = program.data
  const workout = p?.workouts.find((w) => w.id === finished.workoutId)
  const next = p?.workouts.find((w) => w.id === p.next_workout_id)

  return (
    <>
      {workout && finished.newPlan && !answered && (
        <div className="flex flex-col gap-2.5 rounded-2xl border border-border bg-card p-4">
          <div className="flex flex-col gap-1">
            <span className="font-semibold">Update {workoutTitle(workout)}?</span>
            <p className="text-sm text-muted-foreground">Today went differently from the plan. Use today as the plan from now on:</p>
            <ul className="mt-1 text-sm">
              {finished.newPlan.map((e) => (
                <li key={e.name} className="flex justify-between gap-3 py-0.5">
                  <span>{e.name}</span>
                  <span className="font-mono text-xs text-muted-foreground">{planText(e)}</span>
                </li>
              ))}
            </ul>
          </div>
          {change.isError && <p role="alert" className="text-sm text-destructive">{change.error.message}</p>}
          <div className="flex gap-2">
            <button type="button" disabled={change.isPending}
              onClick={() => change.mutate(
                { path: `/workouts/${workout.id}/exercises`, method: 'PUT', body: { exercises: finished.newPlan } },
                { onSuccess: () => setAnswered(true) },
              )}
              className="h-10 rounded-xl bg-primary px-3.5 text-sm font-semibold text-primary-foreground">
              Update workout
            </button>
            <button type="button" onClick={() => setAnswered(true)} className="h-10 rounded-xl border border-border px-3.5 text-sm font-semibold">
              Keep it as is
            </button>
          </div>
        </div>
      )}
      {next && (
        <div className="flex flex-col gap-1 rounded-2xl border border-border bg-card p-4">
          <span className="text-xs font-semibold text-muted-foreground">Next time</span>
          <span className="font-semibold">{workoutTitle(next)}</span>
          <span className="text-sm text-muted-foreground">{next.exercises.map((e) => e.name).join(' · ')}</span>
        </div>
      )}
    </>
  )
}
