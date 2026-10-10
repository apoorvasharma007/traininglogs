import { X } from 'lucide-react'
import { useState } from 'react'
import { useLocation } from 'wouter'
import ConfirmSheet from '@/components/ConfirmSheet'
import { Chevron, Collapse } from '@/components/Collapse'
import CountStepper from '@/components/CountStepper'
import DragList from '@/components/DragList'
import DraftBar from '@/components/DraftBar'
import BottomBar from '@/components/BottomBar'
import HeaderName, { EditButton } from '@/components/HeaderName'
import { LoadError, Loading } from '@/components/QueryStatus'
import ScreenHeader from '@/components/ScreenHeader'
import Sheet from '@/components/Sheet'
import { useEditingFlag } from '@/lib/editing'
import { choicesText, useProgram, useProgramChange, workoutName } from '@/lib/programs'
import PlanSets from '@/components/PlanSets'
import { startSession } from '@/lib/startSession'
import { amountText, COOLDOWN_PRESETS, parseAmount, WARMUP_PRESETS } from '@/lib/movements'
import type { Movement, PlanExercise, Workout } from '@/lib/types'
import { errorText } from '@/lib/errors'
import { BTN } from '@/lib/ui'
import { cn } from '@/lib/utils'
import MovementPicker from '@/components/MovementPicker'

const BLANK: PlanExercise = { name: '', warmup_sets: 0, working_sets: 3, target_reps: null, amrap: true, alternatives: [] }

/** One workout's plan: its name, and each exercise with its sets and target reps. */
type Draft = { name: string; exercises: PlanExercise[]; warmup: Movement[]; cooldown: Movement[] }

/** One workout's plan. Opens for looking; Edit makes a draft that only Save writes. */
export default function WorkoutPlan({ params }: { params: { id: string; wid: string } }) {
  const program = useProgram(params.id)
  const change = useProgramChange(params.id)
  const [, navigate] = useLocation()
  const [draft, setDraft] = useState<Draft | null>(null)
  const startEditing = (w: Workout) =>
    setDraft({ name: workoutName(w), exercises: w.exercises, warmup: w.warmup, cooldown: w.cooldown })
  // Which exercise is open in the drawer: its index, or "new".
  const [editing, setEditing] = useState<number | 'new' | null>(null)
  const [removing, setRemoving] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const w = program.data?.workouts.find((x) => x.id === params.wid)
  const back = `/programs/${params.id}`
  useEditingFlag(draft != null)

  // "Workout N" or nothing means the workout has no name of its own.
  const nameOf = (d: Draft) => (w && d.name.trim().toLowerCase() === `workout ${w.position}` ? '' : d.name.trim())
  const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)
  const nameChanged = !!w && !!draft && nameOf(draft) !== (w.name ?? '')
  const exercisesChanged = !!w && !!draft && !same(draft.exercises, w.exercises)
  const movementsChanged = !!w && !!draft && !(same(draft.warmup, w.warmup) && same(draft.cooldown, w.cooldown))
  const dirty = nameChanged || exercisesChanged || movementsChanged

  async function save() {
    if (!draft || !w) return
    setSaving(true)
    setSaveError(null)
    try {
      if (nameChanged) await change.mutateAsync({ path: `/workouts/${w.id}`, method: 'PATCH', body: { name: nameOf(draft) } })
      if (exercisesChanged) await change.mutateAsync({ path: `/workouts/${w.id}/exercises`, method: 'PUT', body: { exercises: draft.exercises } })
      if (movementsChanged) {
        await change.mutateAsync({ path: `/workouts/${w.id}/movements`, method: 'PUT', body: { warmup: draft.warmup, cooldown: draft.cooldown } })
      }
      setDraft(null)
    } catch (e) {
      setSaveError(errorText(e))
    } finally {
      setSaving(false)
    }
  }

  const exerciseText = (e: PlanExercise) => (
    <>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-[15px] font-semibold">{e.name}</span>
        {e.alternatives.length > 0 && <span className="text-[13px] text-muted-foreground">{choicesText(e)}</span>}
      </span>
      <PlanSets exercise={e} />
    </>
  )
  const exercises = draft?.exercises ?? w?.exercises ?? []

  return (
    <div className={draft ? 'pb-32' : 'pb-6'}>
      <ScreenHeader
        back={draft ? undefined : back}
        backLabel={`Back to ${program.data?.name ?? 'program'}`}
        title={w ? workoutName(w) : 'Workout'}
        titleSlot={draft && w ? (
          <HeaderName label="Workout name" value={draft.name} placeholder={`Workout ${w.position}`} onChange={(name) => setDraft({ ...draft, name })} />
        ) : undefined}
        action={w && !draft && (
          <EditButton onClick={() => startEditing(w)} />
        )}
      />
      {program.isPending && <Loading />}
      {program.isError && <LoadError error={program.error} retry={() => program.refetch()} />}
      {program.data && !w && <p className="px-1 text-[15px] text-muted-foreground">This workout was removed.</p>}
      {w && (
        <div className="flex flex-col gap-4">
          {draft ? (
            <MovementsEditor title="Warm-up" list={draft.warmup} presets={WARMUP_PRESETS} onChange={(warmup) => setDraft({ ...draft, warmup })} />
          ) : (
            <MovementsLine title="Warm-up" list={w.warmup} />
          )}
          {exercises.length === 0 ? (
            <div className="flex flex-col items-start gap-3 rounded-2xl bg-muted p-4 text-[15px]">
              <p className="text-muted-foreground">No exercises yet</p>
              {!draft && (
                <button type="button" onClick={() => startEditing(w)}
                  className={BTN.smallPrimary}>
                  Add Exercises
                </button>
              )}
            </div>
          ) : draft ? (
            <DragList
              items={draft.exercises.map((e, i) => ({ e, key: `${i}-${e.name}` }))}
              keyOf={(x) => x.key}
              label={(x) => x.e.name}
              onReorder={(keys) => setDraft({ ...draft, exercises: keys.map((k) => draft.exercises[Number(k.split('-')[0])]) })}
            >
              {({ e, key }) => (
                <button type="button" onClick={() => setEditing(Number(key.split('-')[0]))}
                  className="flex min-h-14 w-full items-center justify-between gap-3 py-2 pl-4 text-left active:bg-muted">
                  {exerciseText(e)}
                </button>
              )}
            </DragList>
          ) : (
            <section className="flex flex-col gap-1.5">
              <h2 className="px-1 text-[13px] font-semibold">Exercises</h2>
              <ol className="overflow-hidden rounded-2xl border border-border bg-card">
                {w.exercises.map((e, i) => (
                  <li key={i} className="flex min-h-14 items-center gap-3 px-4 py-2 first:border-t-0">
                    <span className="w-4 shrink-0 font-mono text-[13px] text-faint-foreground">{i + 1}</span>
                    {exerciseText(e)}
                  </li>
                ))}
              </ol>
            </section>
          )}

          {draft && (
            <button type="button" onClick={() => setEditing('new')}
              className={BTN.secondary}>
              + Exercise
            </button>
          )}

          {draft ? (
            <MovementsEditor title="Cool-down" list={draft.cooldown} presets={COOLDOWN_PRESETS} onChange={(cooldown) => setDraft({ ...draft, cooldown })} />
          ) : (
            <MovementsLine title="Cool-down" list={w.cooldown} />
          )}

          {draft && (
            <button type="button" onClick={() => setRemoving(true)} className={BTN.danger}>
              Delete Workout
            </button>
          )}
        </div>
      )}

      {w && !draft && w.exercises.length > 0 && program.data && (
        <BottomBar aboveTabs>
          <button type="button"
            onClick={() => startSession({ program: program.data!, workout: w }).then(() => navigate('/session'))}
            className={BTN.primary}>
            Start Workout
          </button>
        </BottomBar>
      )}

      {draft && (
        <DraftBar dirty={dirty} busy={saving} error={saveError} onSave={save}
          onCancel={() => { setDraft(null); setSaveError(null) }} />
      )}

      {draft && (
        <ExerciseSheet
          open={editing != null}
          formKey={String(editing)}
          initial={editing === 'new' || editing == null ? BLANK : draft.exercises[editing]}
          isNew={editing === 'new'}
          busy={false}
          onClose={() => setEditing(null)}
          onSave={(e) => {
            const list = editing === 'new' ? [...draft.exercises, e] : draft.exercises.map((x, i) => (i === editing ? e : x))
            setDraft({ ...draft, exercises: list })
            setEditing(null)
          }}
          onDelete={() => {
            setDraft({ ...draft, exercises: draft.exercises.filter((_, i) => i !== editing) })
            setEditing(null)
          }}
        />
      )}

      <ConfirmSheet open={removing} title={`Delete ${w ? workoutName(w) : 'workout'}?`}
        body="This removes the workout from your program. Sessions you've already logged stay in History."
        confirmLabel="Delete Workout" busy={change.isPending} busyLabel="Deleting…"
        onClose={() => setRemoving(false)}
        onConfirm={() => change.mutate({ path: `/workouts/${params.wid}`, method: 'DELETE' }, { onSuccess: () => { setDraft(null); navigate(back) } })} />
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
    <Sheet open={props.open} onClose={props.onClose} label={props.isNew ? 'Add Exercise' : 'Edit exercise'}>
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
          <input id="exercise-name" autoCapitalize="words" value={e.name} placeholder="Squat"
            onChange={(ev) => set({ name: ev.target.value })}
            className="h-12 rounded-xl border border-border bg-background px-3.5 text-[15px]" />
        </div>
        <Alternatives name={e.name} list={e.alternatives} onChange={(alternatives) => set({ alternatives })} />
        <div className="flex flex-col divide-y divide-border/60 rounded-2xl border border-border px-4">
          <CountStepper label="Warm-up Sets" value={e.warmup_sets} max={20} onChange={(v) => set({ warmup_sets: v })} />
          <CountStepper label="Working Sets" value={e.working_sets} min={1} max={20} onChange={(v) => set({ working_sets: v })} />
          <div className="flex items-center justify-between gap-3 py-2">
            <label htmlFor="target-reps" className="text-[15px]">
              Target Reps
            </label>
            <input id="target-reps" inputMode="numeric" value={e.target_reps ?? ''} placeholder="max"
              onChange={(ev) => {
                const n = parseInt(ev.target.value, 10)
                set(n > 0 ? { target_reps: Math.min(n, 100), amrap: false } : { target_reps: null, amrap: true })
              }}
              className="h-10 w-20 rounded-lg bg-muted text-center font-mono text-[15px] placeholder:text-faint-foreground" />
          </div>
        </div>
        <p className="-mt-2 px-1 text-[13px] text-muted-foreground">Leave empty for AMRAP (as many reps as possible).</p>
        <div className="flex items-center gap-3">
          {/* Like Remove Set: red text. It only changes the draft, which Cancel undoes. */}
          {!props.isNew && (
            <button type="button" disabled={props.busy} onClick={props.onDelete}
              className={BTN.danger}>
              Remove Exercise
            </button>
          )}
          <button type="submit" disabled={props.busy || !e.name.trim()}
            className={cn(BTN.primary, 'flex-1')}>
            {props.busy ? 'Saving…' : props.isNew ? 'Add Exercise' : 'Done'}
          </button>
        </div>
      </form>
    </>
  )
}

/** Other exercises that can take this one's place; the session can switch to them with one tap. */
function Alternatives({ name, list, onChange }: { name: string; list: string[]; onChange: (list: string[]) => void }) {
  const [draft, setDraft] = useState('')
  const add = () => {
    const value = draft.trim()
    const taken = [name, ...list].some((x) => x.trim().toLowerCase() === value.toLowerCase())
    if (value && !taken) onChange([...list, value])
    setDraft('')
  }
  return (
    <div className="flex flex-col gap-1.5">
      <span className="flex flex-col text-[13px] font-semibold">
        Alternatives <span className="font-normal text-muted-foreground">Switch during the workout</span>
      </span>
      {list.map((alt) => (
        <div key={alt} className="flex h-11 items-center justify-between rounded-xl border border-border pr-1 pl-3.5 text-[15px]">
          <span>{alt}</span>
          <button type="button" aria-label={`Remove ${alt}`} onClick={() => onChange(list.filter((x) => x !== alt))}
            className="flex size-10 items-center justify-center text-muted-foreground">
            <X size={18} aria-hidden />
          </button>
        </div>
      ))}
      <div className="flex gap-2">
        <label htmlFor="alternative" className="sr-only">
          Alternative exercise
        </label>
        <input id="alternative" autoCapitalize="words" value={draft} placeholder="Exercise name" onChange={(ev) => setDraft(ev.target.value)}
          onKeyDown={(ev) => {
            if (ev.key === 'Enter') {
              ev.preventDefault()
              add()
            }
          }}
          className="h-11 min-w-0 flex-1 rounded-xl border border-border bg-background px-3.5 text-[15px]" />
        <button type="button" onClick={add} disabled={!draft.trim()}
          className={cn(BTN.smallSecondary, 'h-11')}>
          Add
        </button>
      </div>
    </div>
  )
}

/** A workout's warm-up or cool-down while viewing: a numbered list, or nothing when there is none. */
/** A workout's warm-up or cool-down while viewing it: folded to one row, opened with a tap.
 * Edit shows it in full to change it. */
function MovementsLine({ title, list }: { title: string; list: Movement[] }) {
  const [open, setOpen] = useState(false)
  if (list.length === 0) return null
  return (
    <section className="overflow-hidden rounded-2xl border border-border bg-card">
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)}
        className="flex min-h-13 w-full items-center gap-3 px-4 text-left active:bg-muted">
        <span className="flex-1 text-[15px] font-semibold">{title}</span>
        <span className="text-[13px] text-muted-foreground">{list.length} {list.length === 1 ? 'movement' : 'movements'}</span>
        <Chevron open={open} className="text-muted-foreground" />
      </button>
      <Collapse open={open}>
        <ol className="pb-1.5">
          {list.map((m, i) => (
            <li key={i} className="flex min-h-10 items-center gap-3 px-4 text-[15px] first:border-t-0">
              <span className="w-4 shrink-0 font-mono text-[13px] text-faint-foreground">{i + 1}</span>
              <span className="min-w-0 flex-1">{m.name}</span>
              <span className="shrink-0 font-mono text-[13px] text-muted-foreground">{amountText(m)}</span>
            </li>
          ))}
        </ol>
      </Collapse>
    </section>
  )
}

/** Edits a workout's warm-up or cool-down, as part of the workout's draft. */
function MovementsEditor({
  title,
  list,
  presets,
  onChange,
}: {
  title: string
  list: Movement[]
  presets: { name: string; movements: Movement[] }[]
  onChange: (list: Movement[]) => void
}) {
  type Row = { name: string; amount: string }
  const toRows = (l: Movement[]): Row[] => l.map((m) => ({ name: m.name, amount: amountText(m) }))
  // Rows keep the text as typed ("3 mi" while typing); the draft gets the parsed movements.
  const [rows, setRows] = useState<Row[]>(() => toRows(list))
  const [choosing, setChoosing] = useState(false)
  const save = (next: Row[]) => {
    setRows(next)
    onChange(next.filter((r) => r.name.trim()).map((r) => ({ name: r.name.trim(), ...parseAmount(r.amount) })))
  }
  return (
    <section className="flex flex-col gap-2">
      <h2 className="px-1 text-[15px] font-semibold">{title}</h2>
      {rows.length > 0 && (
        <div className="overflow-hidden rounded-2xl border border-border bg-card">
          {rows.map((r, i) => (
            <div key={i} className="grid min-h-12 grid-cols-[minmax(0,1fr)_96px_44px] items-center gap-1.5 pl-4 first:border-t-0">
              <input aria-label={`${title} movement ${i + 1}`} value={r.name} placeholder="Movement"
                onChange={(e) => save(rows.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))}
                className="h-10 min-w-0 bg-transparent text-[15px] placeholder:text-faint-foreground focus:outline-none" />
              <input aria-label={`${title} amount ${i + 1}`} value={r.amount} placeholder="10 or 3 min"
                onChange={(e) => save(rows.map((x, j) => (j === i ? { ...x, amount: e.target.value } : x)))}
                className="h-10 w-full rounded-lg bg-muted text-center font-mono text-[13px] placeholder:font-sans placeholder:text-[11px] placeholder:text-faint-foreground" />
              <button type="button" aria-label={`Remove ${r.name || 'movement'}`} onClick={() => save(rows.filter((_, j) => j !== i))}
                className="flex size-11 items-center justify-center text-muted-foreground">
                <X size={18} aria-hidden />
              </button>
            </div>
          ))}
        </div>
      )}
      <button type="button" onClick={() => setChoosing(true)} className={BTN.secondary}>
        + Add {title}
      </button>
      <MovementPicker open={choosing} title={title} presets={presets} onClose={() => setChoosing(false)}
        onPreset={(movements) => save([...rows, ...toRows(movements)])} onOwn={() => setRows([...rows, { name: '', amount: '' }])} />
    </section>
  )
}
