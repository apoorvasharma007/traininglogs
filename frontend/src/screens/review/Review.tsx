import { useQueryClient } from '@tanstack/react-query'
import { Ellipsis } from 'lucide-react'
import { useState } from 'react'
import { useLocation } from 'wouter'
import { LoadError, Loading } from '@/components/QueryStatus'
import ScreenHeader from '@/components/ScreenHeader'
import Sheet from '@/components/Sheet'
import { ApiError, api } from '@/lib/api'
import { kg } from '@/lib/format'
import {
  NEW_EXERCISE_NAME,
  draftFromSet,
  draftFromWarmup,
  editsFor,
  exercisePathOf,
  type SetDraft,
} from '@/lib/review'
import type { Card, CardExercise } from '@/lib/types'
import SetSheet from './SetSheet'
import { useReviewDoc } from './useReviewDoc'

type OpenSet = { path: string; title: string; draft: SetDraft }

/** The set at `path` in a card, as an editor draft with its title. */
function findSet(card: Card, path: string): OpenSet | null {
  for (const ex of card.exercises) {
    const w = ex.warmup_rows.find((r) => r.path === path)
    if (w) return { path, title: `${ex.header.name} · Warmup set`, draft: draftFromWarmup(w) }
    const s = ex.working_set_rows.find((r) => r.path === path)
    if (s) return { path, title: `${ex.header.name} · Set ${s.number}`, draft: draftFromSet(s) }
  }
  return null
}

export default function Review({ params }: { params: { id: string } }) {
  const review = useReviewDoc(params.id)
  const queryClient = useQueryClient()
  const [, navigate] = useLocation()
  const [openSet, setOpenSet] = useState<OpenSet | null>(null)
  const [menuFor, setMenuFor] = useState<CardExercise | null>(null)
  const [naming, setNaming] = useState<string | null>(null) // exercise path being renamed
  const [noteFor, setNoteFor] = useState<string | null>(null) // exercise path with its note open
  const [instruction, setInstruction] = useState('')
  const [confirmError, setConfirmError] = useState<string | null>(null)
  const doc = review.doc

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

  async function correct() {
    if (!instruction.trim()) return
    if (await review.run([{ instruction: instruction.trim() }])) setInstruction('')
  }

  async function confirm() {
    if (!doc) return
    setConfirmError(null)
    try {
      const out = await api<{ session_id: string }>(`/extractions/${params.id}/confirm`, {
        method: 'POST',
        body: { extract: doc.extract ?? undefined, corrections: review.corrections.length ? review.corrections : undefined },
      })
      await queryClient.invalidateQueries({ queryKey: ['sessions'] })
      await queryClient.invalidateQueries({ queryKey: ['lifts'] })
      navigate(`/history/${encodeURIComponent(out.session_id)}`)
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      setConfirmError(
        e instanceof ApiError && e.status === 409 ? `${message} Fix the date above, then confirm again.` : message,
      )
    }
  }

  if (review.initial.isPending) return <Loading />
  if (review.initial.isError || !doc) return <LoadError error={review.initial.error} retry={() => review.initial.refetch()} />

  const header = doc.card.session_header
  const dateUnsure = header.uncertain_fields.includes('date')

  return (
    <div className="pb-40">
      <ScreenHeader back="/log" backLabel="Back to your note" title="Review" />

      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-2.5 rounded-2xl border border-border bg-card p-4">
          <div className="flex items-center justify-between gap-3">
            <span className="text-xl font-bold tracking-tight">{header.focus || 'Session'}</span>
            <label className="sr-only" htmlFor="session-date">
              Date
            </label>
            <input
              id="session-date"
              type="date"
              value={header.date}
              disabled={review.busy}
              onChange={(e) =>
                e.target.value && review.run([{ edits: [{ path: header.path, field: 'date', value: e.target.value }] }])
              }
              className={`h-9 rounded-lg border px-2 text-[13px] ${
                dateUnsure ? 'border-warning/50 bg-warning-soft text-warning' : 'border-border bg-background'
              }`}
            />
          </div>
          {dateUnsure && <p className="text-xs text-warning">Check the date: it wasn't clear in your note.</p>}
          {doc.card.warnings.map((w) => (
            <p key={w} className="text-xs text-warning">
              {w}
            </p>
          ))}
        </div>

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
                  {ex.failure_reason && <p className="text-xs text-warning">{ex.failure_reason}</p>}
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

              <div className="grid grid-cols-[34px_70px_60px_minmax(0,1fr)] px-4 text-[11px] font-semibold tracking-wide text-faint-foreground">
                <span>SET</span>
                <span>KG</span>
                <span>REPS</span>
                <span>NOTE</span>
              </div>
              {ex.warmup_rows.map((w) => (
                <SetRow key={w.path} label="W" warmup weight={kg(w.weight_kg) === '0' ? 'BW' : kg(w.weight_kg)}
                  reps={w.rep_count?.toString() ?? '–'} note={w.notes}
                  onOpen={() => setOpenSet(findSet(doc.card, w.path))} />
              ))}
              {ex.working_set_rows.map((s) => (
                <SetRow key={s.path} label={String(s.number)} weight={s.weight_kg ? kg(s.weight_kg) : 'BW'}
                  reps={(s.reps ?? '–') + (s.rpe != null ? ` @${s.rpe}` : '')} note={s.notes}
                  onOpen={() => setOpenSet(findSet(doc.card, s.path))} />
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
      </div>

      {review.error && !openSet && (
        <div role="alert" className="fixed inset-x-4 bottom-44 mx-auto flex max-w-md items-start justify-between gap-3 rounded-2xl bg-destructive px-4 py-3 text-sm text-white">
          <span>{review.error}</span>
          <button type="button" onClick={review.clearError} className="font-semibold">
            OK
          </button>
        </div>
      )}
      {review.canUndo && !review.error && (
        <div role="status" className="fixed inset-x-4 bottom-44 mx-auto flex max-w-md items-center justify-between gap-3 rounded-2xl bg-primary py-1.5 pr-1.5 pl-4 text-sm text-primary-foreground">
          <span>Removed</span>
          <span className="flex">
            <button type="button" onClick={review.undo} className="h-10 px-3.5 font-bold text-accent">
              Undo
            </button>
            <button type="button" onClick={review.dismissUndo} aria-label="Dismiss" className="h-10 px-3 opacity-70">
              ✕
            </button>
          </span>
        </div>
      )}

      <div className="fixed inset-x-0 bottom-0 border-t border-border bg-card">
        <div className="mx-auto flex max-w-md flex-col gap-2.5 px-4 pt-3 pb-[calc(env(safe-area-inset-bottom)+1rem)]">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault()
              correct()
            }}
          >
            <label htmlFor="fix" className="sr-only">
              Describe a change
            </label>
            <input
              id="fix"
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="Or describe a change: all squats were 125"
              className="h-11 min-w-0 flex-1 rounded-xl border border-border bg-background px-3.5 text-sm"
            />
            {instruction.trim() && (
              <button type="submit" disabled={review.busy} className="h-11 rounded-xl border border-border px-3 text-sm font-semibold">
                Apply
              </button>
            )}
          </form>
          {confirmError && (
            <p role="alert" className="text-sm text-destructive">
              {confirmError}
            </p>
          )}
          <button
            type="button"
            disabled={review.busy}
            onClick={confirm}
            className="h-13 rounded-2xl bg-primary font-semibold text-primary-foreground disabled:opacity-50"
          >
            {review.busy ? 'Saving…' : 'Confirm session'}
          </button>
        </div>
      </div>

      {openSet && (
        <SetSheet
          key={openSet.path}
          title={openSet.title}
          initial={openSet.draft}
          busy={review.busy}
          error={review.error}
          onDone={saveSet}
          onDelete={deleteSet}
          onClose={() => {
            setOpenSet(null)
            review.clearError()
          }}
        />
      )}

      <Sheet open={menuFor != null} onClose={() => setMenuFor(null)} label="Exercise options">
        {menuFor && (
          <>
            <span className="text-[17px] font-semibold">{menuFor.header.name}</span>
            <div className="flex flex-col overflow-hidden rounded-2xl border border-border">
              <MenuItem label="Add warmup set" run={() => addLine('add_warmup_set', menuFor.header.path)} />
              <MenuItem label="Add set" run={() => addLine('add_set', menuFor.header.path)} />
              <MenuItem
                label={menuFor.note_preview ? 'Edit note' : 'Add note'}
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
                label="Remove exercise"
                danger
                run={async () => {
                  const path = menuFor.header.path
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

function SetRow(props: { label: string; warmup?: boolean; weight: string; reps: string; note: string | null; onOpen: () => void }) {
  return (
    <button
      type="button"
      onClick={props.onOpen}
      aria-label={`Edit set ${props.label}`}
      className="grid min-h-11.5 w-full grid-cols-[34px_70px_60px_minmax(0,1fr)] items-center border-t border-border px-4 text-left active:bg-background"
    >
      <span className={`font-mono text-[13px] font-semibold ${props.warmup ? 'text-warning' : 'text-muted-foreground'}`}>
        {props.label}
      </span>
      <span className="font-mono text-[15px]">{props.weight}</span>
      <span className="font-mono text-[15px]">{props.reps}</span>
      <span className="truncate text-xs text-muted-foreground">{props.note}</span>
    </button>
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
