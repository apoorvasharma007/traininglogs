import { Pencil } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation } from 'wouter'
import ConfirmSheet from '@/components/ConfirmSheet'
import CountStepper from '@/components/CountStepper'
import DragList from '@/components/DragList'
import NameSheet from '@/components/NameSheet'
import { LoadError, Loading } from '@/components/QueryStatus'
import ScreenHeader from '@/components/ScreenHeader'
import { dayLabel } from '@/lib/format'
import { useProgram, useProgramChange, workoutTitle } from '@/lib/programs'

export default function Program({ params }: { params: { id: string } }) {
  const program = useProgram(params.id)
  const change = useProgramChange(params.id)
  const [, navigate] = useLocation()
  const [renaming, setRenaming] = useState(false)
  const [archiving, setArchiving] = useState(false)
  const p = program.data
  const base = `/programs/${params.id}`

  return (
    <div className="pb-6">
      <ScreenHeader
        back="/programs"
        backLabel="Back to Programs"
        title={p?.name ?? 'Program'}
        action={
          p && (
            <button type="button" aria-label="Rename program" onClick={() => setRenaming(true)}
              className="flex size-11 items-center justify-center text-muted-foreground">
              <Pencil size={18} aria-hidden />
            </button>
          )
        }
      />
      {program.isPending && <Loading />}
      {program.isError && <LoadError error={program.error} retry={() => program.refetch()} />}
      {p && (
        <div className="flex flex-col gap-5">
          {p.following && (
            <span className="self-start rounded-full bg-highlight-soft px-2.5 py-1 text-xs font-semibold text-highlight">
              Following
            </span>
          )}

          <section className="flex flex-col gap-2">
            <h2 className="px-1 text-sm font-semibold">
              Workouts
              {p.workouts.length > 1 && (
                <span className="font-normal text-muted-foreground"> · after {p.workouts.length}, back to 1</span>
              )}
            </h2>
            {p.workouts.length === 0 ? (
              <p className="rounded-2xl border border-dashed border-border p-4 text-sm text-muted-foreground">
                No workouts yet. Add the first one.
              </p>
            ) : (
              <DragList
                items={p.workouts}
                keyOf={(w) => w.id}
                label={workoutTitle}
                onReorder={(ids) => change.mutate({ path: `${base}/workout-order`, method: 'PUT', body: { workout_ids: ids } })}
              >
                {(w) => (
                  <Link href={`${base}/workouts/${w.id}`} className="flex min-h-16 items-center gap-3 py-2 pl-4 active:bg-muted">
                    <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                      <span className="flex items-center gap-2 text-[15px] font-semibold">
                        {workoutTitle(w)}
                        {p.following && w.id === p.next_workout_id && (
                          <span className="rounded-full bg-highlight-soft px-2 py-0.5 text-[11px] font-semibold text-highlight">
                            Next
                          </span>
                        )}
                      </span>
                      <span className="truncate text-xs text-muted-foreground">
                        {w.exercises.length ? w.exercises.map((e) => e.name).join(' · ') : 'No exercises yet'}
                      </span>
                      {w.last_done && <span className="text-xs text-faint-foreground">Last done {dayLabel(w.last_done)}</span>}
                    </span>
                  </Link>
                )}
              </DragList>
            )}
            <button type="button" disabled={change.isPending}
              onClick={() => change.mutate({ path: `${base}/workouts`, method: 'POST', body: {} }, {
                onSuccess: (next) => navigate(`${base}/workouts/${next.workouts[next.workouts.length - 1].id}`),
              })}
              className="h-12 rounded-2xl border border-dashed border-muted-foreground/50 text-sm font-semibold text-muted-foreground transition active:scale-[0.98]">
              + Add workout
            </button>
          </section>

          <section className="flex flex-col gap-2">
            <h2 className="px-1 text-sm font-semibold">Deload reminder</h2>
            <div className="rounded-2xl border border-border bg-card px-4 py-1">
              <CountStepper label="Remind me after" value={p.deload_after_days} min={7} max={84} step={7}
                format={(d) => `${d} days`}
                onChange={(d) => change.mutate({ path: base, method: 'PATCH', body: { deload_after_days: d } })} />
            </div>
          </section>

          {change.isError && <p role="alert" className="px-1 text-sm text-destructive">{change.error.message}</p>}

          <div className="flex flex-col gap-2.5">
            {p.following ? (
              <button type="button" disabled={change.isPending}
                onClick={() => change.mutate({ path: `${base}/unfollow`, method: 'POST' })}
                className="h-12 rounded-2xl border border-border bg-card font-semibold transition active:scale-[0.98]">
                Stop following
              </button>
            ) : (
              <button type="button" disabled={change.isPending}
                onClick={() => change.mutate({ path: `${base}/follow`, method: 'POST' })}
                className="h-13 rounded-2xl bg-primary font-semibold text-primary-foreground transition active:scale-[0.98]">
                Follow this program
              </button>
            )}
            <button type="button" onClick={() => setArchiving(true)} className="h-11 text-sm font-semibold text-destructive">
              Delete program
            </button>
          </div>
        </div>
      )}

      <NameSheet open={renaming} title="Rename program" label="Name" initial={p?.name}
        busy={change.isPending} error={change.error?.message}
        onClose={() => setRenaming(false)}
        onSave={(name) => change.mutate({ path: base, method: 'PATCH', body: { name } }, { onSuccess: () => setRenaming(false) })} />

      <ConfirmSheet open={archiving} title={`Delete ${p?.name ?? 'program'}?`}
        body="It disappears from the app. Sessions you logged from it stay in History."
        confirmLabel="Delete program" busy={change.isPending}
        onClose={() => setArchiving(false)}
        onConfirm={() => change.mutate({ path: base, method: 'DELETE' }, { onSuccess: () => navigate('/programs') })} />
    </div>
  )
}
