import { useQueryClient } from '@tanstack/react-query'
import { ChevronDown, ChevronRight, Ellipsis, MessageSquareText, Pencil, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation } from 'wouter'
import { LoadError, Loading } from '@/components/QueryStatus'
import EffortBars from '@/components/EffortBars'
import NumberBox from '@/components/NumberBox'
import ScreenHeader from '@/components/ScreenHeader'
import BottomBar from '@/components/BottomBar'
import Sheet from '@/components/Sheet'
import { api, ApiError } from '@/lib/api'
import { dayLabel, kg } from '@/lib/format'
import { usePrograms, workoutName } from '@/lib/programs'
import {
  NEW_EXERCISE_NAME,
  draftFromSet,
  draftFromWarmup,
  editsFor,
  exercisePathOf,
  type SetDraft,
} from '@/lib/review'
import type { Card, CardExercise } from '@/lib/types'
import SetSheet, { type SetTarget } from '@/components/SetSheet'
import FixBox from './FixBox'
import { useReviewDoc } from './useReviewDoc'
import { errorText } from '@/lib/errors'

type OpenSet = SetTarget & { path: string }

/** The set at `path` in a card, as an editor draft with its title. */
function findSet(card: Card, path: string): OpenSet | null {
  for (const ex of card.exercises) {
    const w = ex.warmup_rows.find((r) => r.path === path)
    if (w) return { key: path, path, title: ex.header.name, draft: draftFromWarmup(w) }
    const s = ex.working_set_rows.find((r) => r.path === path)
    if (s) return { key: path, path, title: ex.header.name, draft: draftFromSet(s) }
  }
  return null
}

export default function Review({ params }: { params: { id: string } }) {
  const review = useReviewDoc(params.id)
  const queryClient = useQueryClient()
  const [, navigate] = useLocation()
  const [openSet, setOpenSet] = useState<OpenSet | null>(null)
  const [menuFor, setMenuFor] = useState<CardExercise | null>(null)
  const [removed, setRemoved] = useState('') // the Undo toast: "Set removed", "Squat removed"
  const [naming, setNaming] = useState<string | null>(null) // exercise path being renamed
  const [noteFor, setNoteFor] = useState<string | null>(null) // exercise path with its note open
  const [confirmError, setConfirmError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  // A note confirmed before (a retry after a lost answer): the session it was saved as.
  const [savedAs, setSavedAs] = useState<string | null>(null)
  const doc = review.doc
  // Which planned workout this session counts as: the followed program's next one unless changed.
  const followed = usePrograms().data?.find((p) => p.following)
  const [countsAs, setCountsAs] = useState<string | null>(null)
  const workoutId = countsAs ?? followed?.next_workout_id ?? ''
  const countsAsWorkout = followed?.workouts.find((w) => w.id === workoutId) ?? null
  const [picking, setPicking] = useState(false)
  const [timingOpen, setTimingOpen] = useState(false)

  async function saveSet(draft: SetDraft) {
    if (!openSet) return
    const { path, draft: before } = openSet
    let ok: unknown
    if (draft.kind === before.kind) {
      const edits = editsFor(path, before, draft)
      ok = edits.length ? await review.run([{ edits }]) : true
    } else {
      // Warmup and working sets live in separate lists: remove the line, add one of the other
      // kind to the same exercise, then write every value into it.
      ok = await review.run([
        { op: { op: 'remove', path } },
        { op: { op: draft.kind === 'warmup' ? 'add_warmup_set' : 'add_set', path: exercisePathOf(path) } },
        (created, d) => {
          const fresh = created ? findSet(d.card, created) : null
          return fresh && created ? { edits: editsFor(created, fresh.draft, draft) } : null
        },
      ])
    }
    if (ok !== undefined) setOpenSet(null)
  }

  async function deleteSet() {
    if (!openSet) return
    setRemoved('Set removed')
    const ok = await review.run([{ op: { op: 'remove', path: openSet.path } }], { undoable: true })
    if (ok !== undefined) setOpenSet(null)
  }

  async function addLine(op: 'add_set' | 'add_warmup_set', exPath: string) {
    setMenuFor(null)
    const r = await review.run([{ op: { op, path: exPath } }])
    if (r?.created) setOpenSet(findSet(r.doc.card, r.created))
  }

  async function addExercise() {
    const r = await review.run([
      { op: { op: 'add_exercise', path: '' } },
      (c) => (c ? { op: { op: 'add_set', path: c } } : null),
    ])
    if (r?.created) setNaming(exercisePathOf(r.created))
  }

  async function saveField(path: string, field: 'name' | 'notes', value: string, previous: string) {
    if (value.trim() === previous.trim()) return true
    return (await review.run([{ edits: [{ path, field, value: value.trim() }] }])) !== undefined
  }

  /** A value typed into a set's box, saved when the box is left; nothing is sent if unchanged. */
  async function saveValue(path: string, field: 'weight_kg' | 'reps' | 'rep_count', text: string, before: string) {
    const value = text.trim()
    if (value === before) return
    const n = parseFloat(value)
    await review.run([{ edits: [{ path, field, value: field === 'reps' || value === '' || Number.isNaN(n) ? value : n }] }])
  }

  async function confirm() {
    if (!doc) return
    setConfirmError(null)
    setSaving(true)
    try {
      // The session takes its workout's name, or none: History then names it by its exercises.
      const name = followed && countsAsWorkout ? workoutName(countsAsWorkout) : ''
      const named = (header.focus ?? '') === name
        ? { doc, corrections: review.corrections }
        : await review.run([{ edits: [{ path: header.path, field: 'focus', value: name }] }])
      if (!named) return
      const out = await api<{ session_id: string }>(`/extractions/${params.id}/confirm`, {
        method: 'POST',
        body: {
          extract: named.doc.extract ?? undefined,
          corrections: named.corrections.length ? named.corrections : undefined,
          program_workout_id: followed && countsAsWorkout ? countsAsWorkout.id : undefined,
        },
      })
      await queryClient.invalidateQueries({ queryKey: ['sessions'] })
      await queryClient.invalidateQueries({ queryKey: ['programs'] })
      if (followed) await queryClient.invalidateQueries({ queryKey: ['program', followed.id] })
      await queryClient.invalidateQueries({ queryKey: ['lifts'] })
      navigate(`/history/${encodeURIComponent(out.session_id)}`)
    } catch (e) {
      setConfirmError(errorText(e))
      if (e instanceof ApiError && e.status === 409) setSavedAs((e.body as { session_id: string | null }).session_id)
    }
    setSaving(false)
  }

  /** Scrolls to, and focuses, the next value marked amber. */
  function jumpToCheck() {
    const all = Array.from(document.querySelectorAll<HTMLElement>('[data-check]'))
    if (all.length === 0) return
    const next = all.find((el) => el.getBoundingClientRect().top > 140) ?? all[0]
    next.scrollIntoView({ behavior: 'smooth', block: 'center' })
    next.focus?.({ preventScroll: true })
  }

  if (review.initial.isPending) return <Loading />
  if (review.initial.isError || !doc) return <LoadError error={review.initial.error} retry={() => review.initial.refetch()} />

  const header = doc.card.session_header
  const dateUnsure = header.uncertain_fields.includes('date')
  // Everything to look at before confirming: the date, each value the AI wasn't sure of, each
  // working set with no reps, and each exercise it couldn't read.
  const checks =
    (dateUnsure ? 1 : 0) +
    doc.card.exercises.reduce(
      (n, ex) =>
        n +
        (ex.failure_reason ? 1 : 0) +
        ex.warmup_rows.reduce((m, w) => m + (w.uncertain_fields.includes('weight_kg') ? 1 : 0) + (w.uncertain_fields.includes('rep_count') ? 1 : 0), 0) +
        ex.working_set_rows.reduce((m, r) => m + (r.uncertain_fields.includes('weight_kg') ? 1 : 0) + (r.uncertain_fields.includes('reps') || !r.reps ? 1 : 0), 0),
      0,
    )

  return (
    <div className="pb-32">
      <ScreenHeader back="/log" backLabel="Back to your note" title="Review" />

      <div className="flex flex-col gap-3">
        {/* Date, workout and duration as rows: each one taps open to change it. */}
        <div className="overflow-hidden rounded-2xl border border-border bg-card">
          <label data-check={dateUnsure ? '' : undefined}
            className="relative flex min-h-13 items-center gap-3 px-4 text-[15px]">
            <span className="w-20 shrink-0 text-muted-foreground">Date</span>
            <span className={`flex flex-1 flex-col font-semibold ${dateUnsure ? 'text-warning' : ''}`}>
              {dayLabel(header.date)}
              {dateUnsure && <span className="text-xs font-normal">Check this</span>}
            </span>
            <Pencil size={16} aria-hidden className="text-muted-foreground" />
            {/* The phone's date picker sits invisibly over the row and opens on tap. */}
            <input
              aria-label="Date"
              type="date"
              value={header.date}
              disabled={review.busy}
              onChange={(e) =>
                e.target.value && review.run([{ edits: [{ path: header.path, field: 'date', value: e.target.value }] }])
              }
              className="absolute inset-0 cursor-pointer opacity-0"
            />
          </label>
          {followed && followed.workouts.length > 0 && (
            <button type="button" onClick={() => setPicking(true)}
              className="flex min-h-13 w-full items-center gap-3 border-t border-border px-4 text-left text-[15px]">
              <span className="w-20 shrink-0 text-muted-foreground">Workout</span>
              <span className="min-w-0 flex-1 truncate font-semibold">
                {countsAsWorkout ? workoutName(countsAsWorkout) : 'Not Part of a Program'}
                {countsAsWorkout && <span className="ml-1.5 font-normal text-muted-foreground">{followed.name}</span>}
              </span>
              <ChevronRight size={18} aria-hidden className="shrink-0 text-faint-foreground" />
            </button>
          )}
          <button type="button" onClick={() => setTimingOpen(true)}
            className="flex min-h-13 w-full items-center gap-3 border-t border-border px-4 text-left text-[15px]">
            <span className="w-20 shrink-0 text-muted-foreground">Duration</span>
            <span className={`flex-1 ${header.duration_minutes ? 'font-semibold' : 'text-muted-foreground'}`}>
              {header.duration_minutes ? `${header.duration_minutes} min` : 'Add'}
            </span>
            <Pencil size={16} aria-hidden className="text-muted-foreground" />
          </button>
        </div>

        {checks > 0 && (
          <button type="button" onClick={jumpToCheck}
            className="flex h-11 items-center gap-2 self-start rounded-xl border border-warning/50 bg-warning-soft px-3.5 text-sm font-semibold text-warning">
            <TriangleAlert size={16} aria-hidden />
            {checks} {checks === 1 ? 'thing' : 'things'} to check
          </button>
        )}

        {doc.card.exercises.map((ex) => {
          const exPath = ex.header.path
          const isNaming = naming === exPath || ex.header.name === NEW_EXERCISE_NAME
          const note = ex.note_preview?.full_text ?? ''
          return (
            <section key={exPath} className="overflow-hidden rounded-2xl border border-border bg-card">
              <div className="flex items-start justify-between pt-2.5 pr-1 pb-1 pl-4">
                <div className="flex min-w-0 flex-col gap-1 pt-1">
                  {isNaming ? (
                    <InlineField
                      id={`name-${exPath}`}
                      label="Exercise name"
                      initial={ex.header.name === NEW_EXERCISE_NAME ? '' : ex.header.name}
                      autoFocus
                      placeholder="Exercise name"
                      className="text-base font-semibold"
                      onCommit={async (v) => {
                        if (!v.trim()) return
                        if (await saveField(exPath, 'name', v, ex.header.name)) setNaming(null)
                      }}
                    />
                  ) : (
                    <h2 className="text-base font-semibold">{ex.header.name}</h2>
                  )}
                  {ex.failure_reason && (
                    <p data-check="" className="text-[13px] text-warning">Couldn't read the sets. Add them.</p>
                  )}
                </div>
                <button
                  type="button"
                  aria-label={`Options for ${ex.header.name}`}
                  onClick={() => setMenuFor(ex)}
                  className="flex size-11 shrink-0 items-center justify-center text-muted-foreground"
                >
                  <Ellipsis size={20} aria-hidden />
                </button>
              </div>

              {(note || noteFor === exPath) && (
                <div className="px-4 pb-2.5">
                  <InlineField
                    id={`note-${exPath}`}
                    label={`Note for ${ex.header.name}`}
                    initial={note}
                    autoFocus={noteFor === exPath}
                    placeholder="Note for this exercise"
                    className="h-11 w-full rounded-xl border border-muted-foreground/60 bg-card px-3 text-sm"
                    onCommit={async (v) => {
                      if (await saveField(exPath, 'notes', v, note)) setNoteFor(null)
                    }}
                  />
                </div>
              )}

              <div className="grid grid-cols-[56px_minmax(0,1fr)_minmax(0,1fr)] gap-1.5 pr-3 pl-3 text-[11px] font-semibold tracking-wide text-faint-foreground">
                <span className="pl-1">SET</span>
                <span className="text-center">KG</span>
                <span className="text-center">REPS</span>
              </div>
              {ex.warmup_rows.map((w) => (
                <SetRow key={`${w.path}:${w.weight_kg}:${w.rep_count}`} label="W" warmup
                  weight={kg(w.weight_kg)} reps={w.rep_count?.toString() ?? ''} note={w.notes}
                  flagWeight={w.uncertain_fields.includes('weight_kg')} flagReps={w.uncertain_fields.includes('rep_count')}
                  onOpen={() => setOpenSet(findSet(doc.card, w.path))}
                  onWeight={(v) => saveValue(w.path, 'weight_kg', v, kg(w.weight_kg))}
                  onReps={(v) => saveValue(w.path, 'rep_count', v, w.rep_count?.toString() ?? '')} />
              ))}
              {ex.working_set_rows.map((s) => (
                <SetRow key={`${s.path}:${s.weight_kg}:${s.reps}`} label={String(s.number)}
                  weight={s.weight_kg == null ? '' : kg(s.weight_kg)} reps={s.reps ?? ''} rpe={s.rpe} note={s.notes}
                  flagWeight={s.uncertain_fields.includes('weight_kg')} flagReps={s.uncertain_fields.includes('reps') || !s.reps}
                  onOpen={() => setOpenSet(findSet(doc.card, s.path))}
                  onWeight={(v) => saveValue(s.path, 'weight_kg', v, s.weight_kg == null ? '' : kg(s.weight_kg))}
                  onReps={(v) => saveValue(s.path, 'reps', v, s.reps ?? '')} />
              ))}

              <div className="border-t border-border px-3 pt-2 pb-3">
                <button
                  type="button"
                  disabled={review.busy}
                  onClick={() => addLine('add_set', exPath)}
                  className="h-10 rounded-xl border border-dashed border-muted-foreground/50 px-3.5 text-[13px] font-semibold text-muted-foreground"
                >
                  + Set
                </button>
              </div>
            </section>
          )
        })}

        <button
          type="button"
          disabled={review.busy}
          onClick={addExercise}
          className="h-12 rounded-2xl border border-dashed border-muted-foreground/50 text-sm font-semibold text-muted-foreground"
        >
          + Exercise
        </button>

        <FixBox
          busy={review.busy}
          error={review.errorFromFix ? review.error : null}
          onEdit={() => review.error && review.clearError()}
          onFix={async (text) => !!(await review.run([{ instruction: text }]))}
        />
      </div>

      {review.error && !review.errorFromFix && !openSet && (
        <div role="alert" className="fixed inset-x-4 bottom-32 mx-auto flex max-w-md items-start justify-between gap-3 rounded-2xl bg-destructive px-4 py-3 text-sm text-white">
          <span>{review.error}</span>
          <button type="button" onClick={review.clearError} className="font-semibold">
            OK
          </button>
        </div>
      )}
      {review.canUndo && !review.error && (
        <div role="status" className="fixed inset-x-4 bottom-32 mx-auto flex max-w-md items-center justify-between gap-3 rounded-2xl bg-primary py-1.5 pr-1.5 pl-4 text-sm text-primary-foreground">
          <span>{removed}</span>
          <span className="flex">
            <button type="button" onClick={review.undo} className="h-10 px-3.5 font-bold text-highlight">
              Undo
            </button>
            <button type="button" onClick={review.dismissUndo} aria-label="Dismiss" className="h-10 px-3 opacity-70">
              ✕
            </button>
          </span>
        </div>
      )}

      <BottomBar error={confirmError}>
        <button
          type="button"
          disabled={review.busy || saving}
          onClick={confirm}
          className="h-13 rounded-2xl bg-primary font-semibold text-primary-foreground disabled:opacity-50"
        >
          {review.busy || saving ? 'Saving…' : 'Confirm Session'}
        </button>
        {savedAs && (
          <Link href={`/history/${encodeURIComponent(savedAs)}`} className="self-start px-1 text-[13px] font-semibold text-muted-foreground underline underline-offset-2">
            Open it
          </Link>
        )}
      </BottomBar>

      <Sheet open={picking} onClose={() => setPicking(false)} label="Which workout was it?">
        <span className="text-[17px] font-semibold">Which workout was it?</span>
        <div className="flex flex-col overflow-hidden rounded-2xl border border-border">
          {(followed?.workouts ?? []).map((w) => (
            <button key={w.id} type="button" onClick={() => { setCountsAs(w.id); setPicking(false) }}
              className="flex h-13 items-center justify-between border-t border-border px-4 text-left text-[15px] font-medium first:border-t-0">
              {workoutName(w)}
              {w.id === followed?.next_workout_id && <span className="text-xs text-muted-foreground">next</span>}
            </button>
          ))}
          <button type="button" onClick={() => { setCountsAs(''); setPicking(false) }}
            className="flex h-13 items-center border-t border-border px-4 text-left text-[15px] font-medium text-muted-foreground">
            Not Part of a Program
          </button>
        </div>
      </Sheet>

      <DurationSheet open={timingOpen} initial={header.duration_minutes} busy={review.busy}
        onClose={() => setTimingOpen(false)}
        onSave={async (minutes) => {
          if (await review.run([{ edits: [{ path: header.path, field: 'duration_minutes', value: minutes ?? '' }] }])) setTimingOpen(false)
        }} />

      <SetSheet
        target={openSet}
        busy={review.busy}
        error={review.error}
        onDone={saveSet}
        onDelete={deleteSet}
        onClose={() => {
          setOpenSet(null)
          review.clearError()
        }}
      />

      <Sheet open={menuFor != null} onClose={() => setMenuFor(null)} label="Exercise options">
        {menuFor && (
          <>
            <span className="text-[17px] font-semibold">{menuFor.header.name}</span>
            <div className="flex flex-col overflow-hidden rounded-2xl border border-border">
              <MenuItem label="Add Warm-up Set" run={() => addLine('add_warmup_set', menuFor.header.path)} />
              <MenuItem
                label={menuFor.note_preview ? 'Edit Note' : 'Add Note'}
                run={() => {
                  setNoteFor(menuFor.header.path)
                  setMenuFor(null)
                }}
              />
              <MenuItem
                label="Rename"
                run={() => {
                  setNaming(menuFor.header.path)
                  setMenuFor(null)
                }}
              />
              <MenuItem
                label="Remove Exercise"
                danger
                run={async () => {
                  const path = menuFor.header.path
                  setRemoved(`${menuFor.header.name || 'Exercise'} removed`)
                  setMenuFor(null)
                  await review.run([{ op: { op: 'remove', path } }], { undoable: true })
                }}
              />
            </div>
          </>
        )}
      </Sheet>
    </div>
  )
}

/** One set on the card: weight and reps typed in place; the set number opens the full editor. */
function SetRow(props: {
  label: string
  warmup?: boolean
  weight: string
  reps: string
  rpe?: number | null
  note: string | null
  flagWeight?: boolean
  flagReps?: boolean
  onOpen: () => void
  onWeight: (value: string) => void
  onReps: (value: string) => void
}) {
  const [weight, setWeight] = useState(props.weight)
  const [reps, setReps] = useState(props.reps)
  return (
    <div className="grid min-h-13 grid-cols-[56px_minmax(0,1fr)_minmax(0,1fr)] items-center gap-1.5 border-t border-border pr-3 pl-3">
      {/* As on the session screen: effort and a note show as small marks beside the set number. */}
      <button type="button" onClick={props.onOpen} aria-label={`Set ${props.label} options`}
        className={`flex h-10 items-center justify-center gap-1 rounded-lg font-mono text-[13px] font-semibold transition active:scale-95 ${
          props.warmup ? 'text-warning' : 'text-muted-foreground'
        }`}>
        {props.label}
        <EffortBars rpe={props.rpe ?? null} />
        {props.note && <MessageSquareText size={12} strokeWidth={2.2} aria-label="has a note" className="text-foreground" />}
        {!props.note && props.rpe == null && <ChevronDown size={12} strokeWidth={2.5} aria-hidden className="opacity-60" />}
      </button>
      <NumberBox label={`Weight for set ${props.label}`} value={weight} placeholder="kg" flagged={props.flagWeight && weight === props.weight}
        onChange={setWeight} onBlur={() => props.onWeight(weight)} />
      <NumberBox label={`Reps for set ${props.label}`} value={reps} placeholder="reps" inputMode="numeric" flagged={props.flagReps && reps === props.reps}
        onChange={setReps} onBlur={() => props.onReps(reps)} />
    </div>
  )
}

function MenuItem({ label, run, danger }: { label: string; run: () => void; danger?: boolean }) {
  return (
    <button
      type="button"
      onClick={run}
      className={`h-13 border-t border-border px-4 text-left text-[15px] font-medium first:border-t-0 ${
        danger ? 'text-destructive' : ''
      }`}
    >
      {label}
    </button>
  )
}

/** A text field that saves when you leave it or press Enter. */
function InlineField(props: {
  id: string
  label: string
  initial: string
  placeholder: string
  className: string
  autoFocus?: boolean
  onCommit: (value: string) => void
}) {
  const [value, setValue] = useState(props.initial)
  return (
    <>
      <label htmlFor={props.id} className="sr-only">
        {props.label}
      </label>
      <input
        id={props.id}
        autoFocus={props.autoFocus}
        value={value}
        placeholder={props.placeholder}
        onChange={(e) => setValue(e.target.value)}
        onBlur={() => props.onCommit(value)}
        onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
        className={props.className}
      />
    </>
  )
}

/** How long the session took, in minutes; empty clears it. */
function DurationSheet(props: { open: boolean; initial: number | null; busy: boolean; onSave: (minutes: number | null) => void; onClose: () => void }) {
  return (
    <Sheet open={props.open} onClose={props.onClose} label="Duration">
      {props.open && <DurationForm {...props} />}
    </Sheet>
  )
}

function DurationForm({ initial, busy, onSave }: { initial: number | null; busy: boolean; onSave: (minutes: number | null) => void }) {
  const [text, setText] = useState(initial ? String(initial) : '')
  return (
    <form className="flex flex-col gap-4" onSubmit={(e) => {
      e.preventDefault()
      const n = parseInt(text, 10)
      onSave(n > 0 ? n : null)
    }}>
      <span className="text-[17px] font-semibold">How long was it?</span>
      <div className="flex items-baseline justify-center gap-2">
        <label htmlFor="duration" className="sr-only">Minutes</label>
        <input id="duration" autoFocus inputMode="numeric" value={text} onChange={(e) => setText(e.target.value.replace(/\D/g, ''))}
          className="h-14 w-28 rounded-xl bg-muted text-center font-mono text-[28px] font-semibold" />
        <span className="text-muted-foreground">min</span>
      </div>
      <button type="submit" disabled={busy} className="h-13 rounded-2xl bg-primary font-semibold text-primary-foreground disabled:opacity-50">
        Save
      </button>
    </form>
  )
}
