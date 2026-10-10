import { Check } from 'lucide-react'
import Parts from '@/components/Parts'
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'wouter'
import ConfirmSheet from '@/components/ConfirmSheet'
import BottomBar from '@/components/BottomBar'
import { applyChanges, isRemoval } from '@/lib/planChanges'
import { useProgram, useProgramChange, workoutName } from '@/lib/programs'
import { useOutbox } from '@/lib/store'
import { clearLastFinished, getLastFinished, loadLastFinished, setLastFinished, type Finished } from '@/screens/session/finished'
import { errorText } from '@/lib/errors'

/** After Finish: whether the session reached the server, an offer to update the workout, next time. */
export default function Done() {
  const [finished, setFinished] = useState(getLastFinished)
  const outbox = useOutbox()
  const [, navigate] = useLocation()

  // After the app restarts on this screen, the summary comes back from the phone; with none
  // there's nothing to show, so it goes to Train.
  useEffect(() => {
    if (finished) return
    loadLastFinished().then((f) => (f ? setFinished(f) : navigate('/', { replace: true })))
  }, [finished, navigate])

  if (!finished) return null
  const waiting = outbox.pending.some((r) => r.client_id === finished.clientId)

  return (
    <div className="flex min-h-dvh flex-col gap-4 pt-16 pb-8">
      <div className="flex flex-col gap-1.5 px-1">
        <span className="flex size-11 items-center justify-center rounded-full bg-highlight text-background">
          <Check size={22} strokeWidth={2.6} aria-hidden />
        </span>
        <h1 className="mt-2 text-[28px] font-bold tracking-tight">Session Done</h1>
        <Parts className="justify-center text-sm text-muted-foreground" items={[
          finished.title, `${finished.minutes} min`, `${finished.sets} ${finished.sets === 1 ? 'set' : 'sets'}`,
        ]} />
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

      <BottomBar>
        <Link href="/" onClick={() => clearLastFinished()}
          className="flex h-13 items-center justify-center rounded-2xl bg-primary font-semibold text-primary-foreground transition active:scale-[0.98]">
          Done
        </Link>
      </BottomBar>
    </div>
  )
}

function ProgramCards({ finished, programId }: { finished: Finished; programId: string }) {
  const program = useProgram(programId)
  const change = useProgramChange(programId)
  const [chosen, setChosen] = useState(() => new Set(finished.changes.filter((c) => c.on).map((c) => c.id)))
  // Answered before a restart: not asked again.
  const [state, setState] = useState<'asking' | 'saving' | 'saved' | 'kept'>(finished.answered ? 'kept' : 'asking')
  const answer = (next: 'saved' | 'kept') => {
    setState(next)
    setLastFinished({ ...finished, answered: true })
  }
  const [error, setError] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)
  const p = program.data
  const next = p?.workouts.find((w) => w.id === p.next_workout_id)
  const workout = finished.workout

  async function save() {
    if (!workout) return
    setState('saving')
    setError(null)
    const plan = applyChanges(workout, finished.changes, chosen)
    try {
      if (plan.exercisesChanged) {
        await change.mutateAsync({ path: `/workouts/${workout.id}/exercises`, method: 'PUT', body: { exercises: plan.exercises } })
      }
      if (plan.movementsChanged) {
        await change.mutateAsync({ path: `/workouts/${workout.id}/movements`, method: 'PUT', body: { warmup: plan.warmup, cooldown: plan.cooldown } })
      }
      answer('saved')
    } catch (e) {
      setError(errorText(e))
      setState('asking')
    }
  }

  return (
    <>
      {workout && finished.changes.length > 0 && state !== 'kept' && (
        <div className="flex flex-col gap-3 rounded-2xl border border-border bg-card p-4">
          {state === 'saved' ? (
            <p className="text-sm"><span className="font-semibold">Program updated.</span> {workoutName(workout)} includes these from now on.</p>
          ) : (
            <>
              <span className="flex flex-col">
                <span className="font-semibold">Update the program?</span>
                <span className="text-xs text-muted-foreground">Tick what {workoutName(workout)} should include from now on.</span>
              </span>
              <ul className="flex flex-col">
                {finished.changes.map((c) => (
                  <li key={c.id}>
                    {/* Ticked like a set: the same circle, the whole row is the button. */}
                    <button type="button" role="checkbox" aria-checked={chosen.has(c.id)} aria-label={c.label}
                      onClick={() => setChosen((set) => {
                        const n = new Set(set)
                        if (n.has(c.id)) n.delete(c.id)
                        else n.add(c.id)
                        return n
                      })}
                      className="flex min-h-11 w-full items-center gap-3 text-left text-sm active:opacity-70">
                      <span className={`flex size-6 shrink-0 items-center justify-center rounded-lg border-[1.5px] transition-colors ${
                        chosen.has(c.id) ? 'border-highlight bg-highlight text-background' : 'border-border text-transparent'
                      }`}>
                        <Check size={14} strokeWidth={3} aria-hidden />
                      </span>
                      <span className={isRemoval(c) ? 'text-destructive' : ''}>{c.label}</span>
                    </button>
                  </li>
                ))}
              </ul>
              {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
              <div className="flex items-center gap-2">
                <button type="button" disabled={state === 'saving' || chosen.size === 0} onClick={() => setConfirming(true)}
                  className="h-11 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-40">
                  {state === 'saving' ? 'Saving…' : 'Update Program'}
                </button>
                <button type="button" onClick={() => answer('kept')} className="h-11 px-3 text-sm font-semibold text-muted-foreground">
                  Keep as Is
                </button>
              </div>
            </>
          )}
        </div>
      )}
      {workout && (
        <ConfirmSheet open={confirming} tone="primary" title={`Update ${workoutName(workout)}?`}
          body={`${chosen.size} ${chosen.size === 1 ? 'change' : 'changes'} will apply to every session of ${workoutName(workout)} from now on. Sessions you've already logged stay as they are.`}
          confirmLabel="Update Program" busy={state === 'saving'}
          onClose={() => setConfirming(false)}
          onConfirm={() => { setConfirming(false); save() }} />
      )}
      {next && (
        <div className="flex flex-col gap-1 rounded-2xl border border-border bg-card p-4">
          <span className="text-xs font-semibold text-muted-foreground">Next Time</span>
          <span className="font-semibold">{workoutName(next)}</span>
          <Parts className="text-sm text-muted-foreground" items={next.exercises.map((e) => e.name)} />
        </div>
      )}
    </>
  )
}
