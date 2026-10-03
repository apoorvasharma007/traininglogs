import { useState } from 'react'
import { useLocation } from 'wouter'
import ConfirmSheet from '@/components/ConfirmSheet'
import CountStepper from '@/components/CountStepper'
import DragList from '@/components/DragList'
import { LoadError, Loading } from '@/components/QueryStatus'
import ScreenHeader from '@/components/ScreenHeader'
import Sheet from '@/components/Sheet'
import { planText, useProgram, useProgramChange } from '@/lib/programs'
import { startSession } from '@/lib/startSession'
import type { PlanExercise } from '@/lib/types'

const BLANK: PlanExercise = { name: '', warmup_sets: 0, working_sets: 3, target_reps: 5, amrap: false }

/** One workout's plan: its name, and each exercise with its sets and target reps. */
export default function WorkoutPlan({ params }: { params: { id: string; wid: string } }) {
  const program = useProgram(params.id)
  const change = useProgramChange(params.id)
  const [, navigate] = useLocation()
  // Which exercise is open in the editor: its index, or "new".
  const [editing, setEditing] = useState<number | 'new' | null>(null)
  const [removing, setRemoving] = useState(false)
  const w = program.data?.workouts.find((x) => x.id === params.wid)
  const back = `/programs/${params.id}`

  function saveExercises(exercises: PlanExercise[], then?: () => void) {
    change.mutate({ path: `/workouts/${params.wid}/exercises`, method: 'PUT', body: { exercises } }, { onSuccess: then })
  }

  return (
    <div className="pb-6">
      <ScreenHeader back={back} backLabel={`Back to ${program.data?.name ?? 'program'}`} title={w ? `Workout ${w.position}` : 'Workout'} />
      {program.isPending && <Loading />}
      {program.isError && <LoadError error={program.error} retry={() => program.refetch()} />}
      {program.data && !w && <p className="px-1 text-sm text-muted-foreground">This workout was removed.</p>}
      {w && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="workout-name" className="px-1 text-[13px] font-semibold">
              Name
            </label>
            <input id="workout-name" key={w.name ?? ''} defaultValue={w.name ?? ''} placeholder="Push, Pull, Legs…"
              onBlur={(e) => {
                if (e.target.value.trim() !== (w.name ?? '')) {
                  change.mutate({ path: `/workouts/${w.id}`, method: 'PATCH', body: { name: e.target.value } })
                }
              }}
              onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
              className="h-12 rounded-xl border border-border bg-card px-3.5 text-[15px]" />
          </div>

          {w.exercises.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-border p-4 text-sm text-muted-foreground">
              No exercises yet. Add what this workout is made of; weights come from what you lifted last time.
            </p>
          ) : (
            <DragList
              items={w.exercises.map((e, i) => ({ e, key: String(i) }))}
              keyOf={(x) => x.key}
              label={(x) => x.e.name}
              onReorder={(keys) => saveExercises(keys.map((k) => w.exercises[Number(k)]))}
            >
              {({ e, key }) => (
                <button type="button" onClick={() => setEditing(Number(key))}
                  className="flex min-h-14 w-full items-center justify-between gap-3 py-2 pl-4 text-left active:bg-muted">
                  <span className="text-[15px] font-semibold">{e.name}</span>
                  <span className="font-mono text-[13px] text-muted-foreground">{planText(e)}</span>
                </button>
              )}
            </DragList>
          )}

          <button type="button" onClick={() => setEditing('new')}
            className="h-12 rounded-2xl border border-dashed border-muted-foreground/50 text-sm font-semibold text-muted-foreground transition active:scale-[0.98]">
            + Exercise
          </button>

          {change.isError && <p role="alert" className="px-1 text-sm text-destructive">{change.error.message}</p>}

          {w.exercises.length > 0 && program.data && (
            <button type="button"
              onClick={() => startSession({ program: program.data, workout: w }).then(() => navigate('/session'))}
              className="h-13 rounded-2xl bg-primary font-semibold text-primary-foreground transition active:scale-[0.98]">
              Start workout
            </button>
          )}

          <button type="button" onClick={() => setRemoving(true)} className="h-11 text-sm font-semibold text-destructive">
            Remove workout
          </button>
        </div>
      )}

      {w && (
        <ExerciseSheet
          open={editing != null}
          formKey={String(editing)}
          initial={editing === 'new' || editing == null ? BLANK : w.exercises[editing]}
          isNew={editing === 'new'}
          busy={change.isPending}
          onClose={() => setEditing(null)}
          onSave={(e) => {
            const list = editing === 'new' ? [...w.exercises, e] : w.exercises.map((x, i) => (i === editing ? e : x))
            saveExercises(list, () => setEditing(null))
          }}
          onDelete={() => saveExercises(w.exercises.filter((_, i) => i !== editing), () => setEditing(null))}
        />
      )}

      <ConfirmSheet open={removing} title={`Remove workout ${w?.position ?? ''}?`}
        body="The workouts after it move up one. Sessions you logged from it stay in History."
        confirmLabel="Remove workout" busy={change.isPending}
        onClose={() => setRemoving(false)}
        onConfirm={() => change.mutate({ path: `/workouts/${params.wid}`, method: 'DELETE' }, { onSuccess: () => navigate(back) })} />
    </div>
  )
}

function ExerciseSheet(props: {
  open: boolean
  formKey: string
  initial: PlanExercise
  isNew: boolean
  busy: boolean
  onSave: (e: PlanExercise) => void
  onDelete: () => void
  onClose: () => void
}) {
  // Mounted closed and opened in place: a drawer created already open doesn't slide into view.
  return (
    <Sheet open={props.open} onClose={props.onClose} label={props.isNew ? 'Add exercise' : 'Edit exercise'}>
      {props.open && <ExerciseForm key={props.formKey} {...props} />}
    </Sheet>
  )
}

function ExerciseForm(props: {
  initial: PlanExercise
  isNew: boolean
  busy: boolean
  onSave: (e: PlanExercise) => void
  onDelete: () => void
  onClose: () => void
}) {
  const [e, setE] = useState(props.initial)
  const set = (patch: Partial<PlanExercise>) => setE((x) => ({ ...x, ...patch }))
  return (
    <>
      <form className="flex flex-col gap-4" onSubmit={(ev) => {
        ev.preventDefault()
        if (e.name.trim()) props.onSave({ ...e, name: e.name.trim() })
      }}>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="exercise-name" className="text-[13px] font-semibold">
            Exercise
          </label>
          <input id="exercise-name" autoFocus={props.isNew} value={e.name} placeholder="Squat"
            onChange={(ev) => set({ name: ev.target.value })}
            className="h-12 rounded-xl border border-border bg-background px-3.5 text-[15px]" />
        </div>
        <div className="flex flex-col divide-y divide-border rounded-2xl border border-border px-4">
          <CountStepper label="Warmup sets" value={e.warmup_sets} max={20} onChange={(v) => set({ warmup_sets: v })} />
          <CountStepper label="Working sets" value={e.working_sets} min={1} max={20} onChange={(v) => set({ working_sets: v })} />
          <div className="flex items-center justify-between py-2">
            <span className="text-[15px]">Reps</span>
            <div role="group" aria-label="Reps target" className="grid grid-cols-2 rounded-xl bg-muted p-0.5">
              {(['target', 'max'] as const).map((k) => {
                const on = k === 'max' ? e.amrap : !e.amrap
                return (
                  <button key={k} type="button" aria-pressed={on}
                    onClick={() => set(k === 'max' ? { amrap: true, target_reps: null } : { amrap: false, target_reps: e.target_reps ?? 5 })}
                    className={`h-9 rounded-[10px] px-3 text-[13px] font-semibold ${on ? 'bg-card shadow-sm' : 'text-muted-foreground'}`}>
                    {k === 'max' ? 'As many as you can' : 'Target'}
                  </button>
                )
              })}
            </div>
          </div>
          {!e.amrap && (
            <CountStepper label="Target reps" value={e.target_reps ?? 5} min={1} max={100}
              onChange={(v) => set({ target_reps: v })} />
          )}
        </div>
        <div className="flex gap-2.5">
          {!props.isNew && (
            <button type="button" disabled={props.busy} onClick={props.onDelete}
              className="h-13 rounded-2xl border border-destructive/40 px-4 font-semibold text-destructive disabled:opacity-50">
              Delete
            </button>
          )}
          <button type="submit" disabled={props.busy || !e.name.trim()}
            className="h-13 flex-1 rounded-2xl bg-primary font-semibold text-primary-foreground transition active:scale-[0.98] disabled:opacity-50">
            {props.busy ? 'Saving…' : props.isNew ? 'Add' : 'Done'}
          </button>
        </div>
      </form>
    </>
  )
}
