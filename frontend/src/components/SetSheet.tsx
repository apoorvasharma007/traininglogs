import { useState } from 'react'
import NoteBox from '@/components/NoteBox'
import NumberBox from '@/components/NumberBox'
import Sheet from '@/components/Sheet'
import { EFFORT_FILL, EFFORT_OUTLINE, EFFORTS, effortLevel } from '@/lib/effort'
import { kg } from '@/lib/format'
import { RPES, type SetDraft, type SetKind } from '@/lib/review'
import { MAX_RAMP, rampSets } from '@/lib/session'
import { BTN, SHEET_TITLE } from '@/lib/ui'
import { cn } from '@/lib/utils'

// rampFrom: the first working set's weight, to suggest as a warm-up ramp's target (live sessions only).
export type SetTarget = { key: string; title: string; draft: SetDraft; last?: string | null; rampFrom?: number | null }

/**
 * Edits one set: weight, reps, RPE, warmup or working, note. Nothing is saved until Done.
 * The drawer stays mounted and opens when `target` is set: created already open, it would not
 * slide into view until something else re-rendered.
 */
export default function SetSheet({
  target,
  busy,
  error,
  onDone,
  onDelete,
  onClose,
  onRamp,
}: {
  target: SetTarget | null
  busy: boolean
  error: string | null
  onDone: (draft: SetDraft) => void
  onDelete: () => void
  onClose: () => void
  /** Adds warm-up sets to the set's exercise; without it the Warm-up tab offers no ramp. */
  onRamp?: (ramp: ({ kg: number; reps: number } | null)[]) => void
}) {
  // Keeps showing the last set while the drawer slides away.
  const [shown, setShown] = useState(target)
  if (target && target !== shown) setShown(target)
  return (
    <Sheet open={target != null} onClose={onClose} label="Edit set">
      {shown && (
        <SetForm key={shown.key} title={shown.title} last={shown.last ?? null} initial={shown.draft} busy={busy} error={error}
          onDone={onDone} onDelete={onDelete} rampFrom={shown.rampFrom ?? null} onRamp={onRamp} />
      )}
    </Sheet>
  )
}

function SetForm({
  title,
  last,
  initial,
  busy,
  error,
  onDone,
  onDelete,
  rampFrom,
  onRamp,
}: {
  title: string
  last: string | null
  initial: SetDraft
  busy: boolean
  error: string | null
  onDone: (draft: SetDraft) => void
  onDelete: () => void
  rampFrom: number | null
  onRamp?: (ramp: ({ kg: number; reps: number } | null)[]) => void
}) {
  // Weight and reps are typed on the set's row; the drawer holds what the row can't show.
  const [draft, setDraft] = useState(initial)
  const set = (patch: Partial<SetDraft>) => setDraft((d) => ({ ...d, ...patch }))

  return (
    <>
      <span className="flex min-w-0 flex-col">
        <span className={`truncate ${SHEET_TITLE}`}>{title}</span>
        {last && <span className="text-[13px] text-muted-foreground">Last time {last}</span>}
      </span>
      <div role="group" aria-label="Set type" className="grid grid-cols-2 gap-1 rounded-2xl bg-muted p-1">
        {(['warmup', 'working'] as SetKind[]).map((k) => (
          <button key={k} type="button" aria-pressed={draft.kind === k} onClick={() => set({ kind: k })}
            className={`h-11 rounded-xl text-[15px] font-semibold ${
              draft.kind === k ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground'
            }`}>
            {k === 'warmup' ? 'Warm-up' : 'Working'}
          </button>
        ))}
      </div>

      {/* Both tabs share one grid cell; the one not shown stays invisible but keeps its height, so
          switching Warm-up and Working never changes the sheet's size. */}
      <div className="grid grid-cols-[minmax(0,1fr)]">
        <div aria-hidden={draft.kind !== 'warmup'} className={`col-start-1 row-start-1 flex min-w-0 flex-col ${draft.kind === 'warmup' ? '' : 'invisible'}`}>
          {onRamp ? (
            <WarmupSets from={rampFrom} onAdd={onRamp} />
          ) : (
            <div className="flex flex-1 items-center justify-center rounded-2xl bg-muted text-[15px] text-muted-foreground">
              Warm-up sets don't track effort
            </div>
          )}
        </div>
        <div aria-hidden={draft.kind !== 'working'} className={`col-start-1 row-start-1 flex min-w-0 flex-col ${draft.kind === 'working' ? '' : 'invisible'}`}>
          {/* The three words with the exact RPE numbers under them. Tap a chosen one again to clear it. */}
          <div role="group" aria-label="Effort" className="flex flex-col gap-2.5">
            <div className="grid grid-cols-3 gap-2">
              {EFFORTS.map((e) => {
                const on = effortLevel(draft.rpe) === e.level
                return (
                  <button key={e.level} type="button" aria-pressed={on} onClick={() => set({ rpe: on ? null : e.rpe })}
                    className={`h-14 rounded-2xl text-base font-semibold transition-colors ${on ? EFFORT_FILL[e.level] : 'bg-muted text-foreground'}`}>
                    {e.label}
                  </button>
                )
              })}
            </div>
            <div className="scrollbar-none -mr-5 flex gap-2 overflow-x-auto pr-5">
              {RPES.map((r) => {
                const on = draft.rpe === r
                const level = effortLevel(r) as 1 | 2 | 3
                return (
                  <button key={r} type="button" aria-pressed={on} aria-label={`RPE ${r}`} onClick={() => set({ rpe: on ? null : r })}
                    className={`h-11 w-13 shrink-0 rounded-xl font-mono text-[15px] font-semibold ${
                      on ? EFFORT_FILL[level] : `border-[1.5px] bg-card ${EFFORT_OUTLINE[level]}`
                    }`}>
                    {r}
                  </button>
                )
              })}
            </div>
          </div>
        </div>
      </div>

      <label htmlFor="set-note" className="sr-only">
        Note
      </label>
      <NoteBox id="set-note" value={draft.note} placeholder={draft.kind === 'warmup' ? 'Warm-up Set Note' : 'Working Set Note'} onChange={(e) => set({ note: e.target.value })}
        className="min-h-11 rounded-xl bg-muted px-3.5 text-[15px] placeholder:text-faint-foreground" />

      {error && (
        <p role="alert" className="text-[15px] text-destructive">
          {error}
        </p>
      )}

      <div className="flex items-center gap-3">
        <button type="button" disabled={busy} onClick={onDelete} className={BTN.danger}>
          Remove Set
        </button>
        <button type="button" disabled={busy} onClick={() => onDone(draft)} className={cn(BTN.primary, 'flex-1')}>
          {busy ? 'Saving…' : 'Done'}
        </button>
      </div>
    </>
  )
}

/**
 * Warm-up sets for the set's exercise, added in one tap: as many as the count says, blank to fill
 * in later, or, with a weight to work up to, a ramp rounded to 2.5 kg. The weight box shows the
 * first working weight in grey; one tap takes it.
 */
function WarmupSets({ from, onAdd }: { from: number | null; onAdd: (ramp: ({ kg: number; reps: number } | null)[]) => void }) {
  const [target, setTarget] = useState('')
  const [count, setCount] = useState(3)
  const weight = parseFloat(target)
  const ramp = weight > 0 ? rampSets(weight, count) : []
  const step = 'h-11 w-11 rounded-xl text-[22px] font-semibold disabled:opacity-30'
  return (
    <div className="flex flex-col gap-2.5">
      <div className="grid grid-cols-2 gap-2.5">
        <div className="flex flex-col gap-1 text-[13px] font-semibold text-muted-foreground">
          How Many
          <span className="flex h-12 items-center justify-between rounded-xl bg-muted px-0.5 text-foreground">
            <button type="button" aria-label="Fewer sets" disabled={count <= 1} onClick={() => setCount(count - 1)} className={step}>−</button>
            <span className="font-mono text-[17px]">{count}</span>
            <button type="button" aria-label="More sets" disabled={count >= MAX_RAMP} onClick={() => setCount(count + 1)} className={step}>+</button>
          </span>
        </div>
        <label className="flex flex-col gap-1 text-[13px] font-semibold text-muted-foreground">
          Work Up To (kg)
          <NumberBox label="Work up to, kg" value={target} placeholder={from ? kg(from) : 'optional'} fillable={from != null}
            onChange={setTarget} className="h-12 rounded-xl text-[17px] font-semibold text-foreground" />
        </label>
      </div>
      {ramp.length > 0 && (
        <p aria-label="Ramp" className="scrollbar-none flex min-h-6 items-center gap-1.5 overflow-x-auto font-mono text-[15px] font-semibold whitespace-nowrap">
          {ramp.map((r, i) => (
            <span key={i} className="flex items-center gap-1.5">
              {i > 0 && <span aria-hidden className="text-faint-foreground">→</span>}
              {kg(r.kg)}×{r.reps}
            </span>
          ))}
        </p>
      )}
      <button type="button" onClick={() => onAdd(ramp.length ? ramp : Array(count).fill(null))}
        className={BTN.primary}>
        Add {count} {count === 1 ? 'Set' : 'Sets'}
      </button>
    </div>
  )
}
