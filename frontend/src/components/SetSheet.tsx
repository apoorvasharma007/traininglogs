import { useState } from 'react'
import Sheet from '@/components/Sheet'
import { EFFORT_FILL, EFFORT_OUTLINE, EFFORTS, effortLevel } from '@/lib/effort'
import { kg } from '@/lib/format'
import { RPES, type SetDraft, type SetKind } from '@/lib/review'
import { MAX_RAMP, rampSets } from '@/lib/session'

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
  onRamp?: (ramp: { kg: number; reps: number }[]) => void
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
  onRamp?: (ramp: { kg: number; reps: number }[]) => void
}) {
  // Weight and reps are typed on the set's row; the drawer holds what the row can't show.
  const [draft, setDraft] = useState(initial)
  const set = (patch: Partial<SetDraft>) => setDraft((d) => ({ ...d, ...patch }))

  return (
    <>
      <span className="flex min-w-0 flex-col">
        <span className="truncate text-[18px] font-semibold">{title}</span>
        {last && <span className="text-[13px] text-muted-foreground">Last time {last}</span>}
      </span>
      <div role="group" aria-label="Set type" className="grid grid-cols-2 gap-1 rounded-[14px] bg-muted p-1">
        {(['warmup', 'working'] as SetKind[]).map((k) => (
          <button key={k} type="button" aria-pressed={draft.kind === k} onClick={() => set({ kind: k })}
            className={`h-11 rounded-[11px] text-[15px] font-semibold ${
              draft.kind === k ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground'
            }`}>
            {k === 'warmup' ? 'Warm-up' : 'Working'}
          </button>
        ))}
      </div>

      {/* Both tabs are the same height, so switching doesn't move the buttons under your finger. */}
      <div className="h-[12.5rem]">
        {draft.kind === 'warmup' &&
          (onRamp ? (
            <RampUp from={rampFrom} onAdd={onRamp} />
          ) : (
            <div className="flex h-full items-center justify-center rounded-xl bg-muted/50 text-sm text-muted-foreground">
              Warm-up sets don't track effort
            </div>
          ))}
        {draft.kind === 'working' && (
          // Tap a word for its usual RPE, or a number under it to be exact; tap the chosen one again to clear.
          <div role="group" aria-label="Effort" className="flex flex-col gap-2.5">
            <span className="text-[13px] font-semibold text-muted-foreground">How hard was it?</span>
            <div className="grid grid-cols-3 gap-2">
              {EFFORTS.map((e) => {
                const on = effortLevel(draft.rpe) === e.level
                return (
                  <button key={e.level} type="button" aria-pressed={on} onClick={() => set({ rpe: on ? null : e.rpe })}
                    className={`flex h-17 flex-col items-center justify-center gap-0.5 rounded-[14px] transition-colors ${on ? EFFORT_FILL[e.level] : 'bg-muted text-foreground'}`}>
                    <span className="text-base font-semibold">{e.label}</span>
                    <span className={`text-xs ${on ? '' : 'text-muted-foreground'}`}>{e.means}</span>
                  </button>
                )
              })}
            </div>
            <div className="-mr-5 flex gap-2 overflow-x-auto pr-5 pb-1">
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
        )}
      </div>

      <label htmlFor="set-note" className="sr-only">
        Note
      </label>
      <input id="set-note" value={draft.note} placeholder="Note" onChange={(e) => set({ note: e.target.value })}
        className="h-11 rounded-xl bg-muted px-3.5 text-[15px] placeholder:text-faint-foreground" />

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="flex items-center justify-between gap-3">
        <button type="button" disabled={busy} onClick={onDelete}
          className="h-11 px-1 text-[15px] font-semibold text-destructive disabled:opacity-50">
          Remove Set
        </button>
        <button type="button" disabled={busy} onClick={() => onDone(draft)}
          className="h-12 min-w-32 rounded-2xl bg-primary px-6 font-semibold text-primary-foreground transition active:scale-[0.98] disabled:opacity-50">
          {busy ? 'Saving…' : 'Done'}
        </button>
      </div>
    </>
  )
}

/** A ramp of warm-up sets up to a working weight, added to the set's exercise in one tap. */
function RampUp({ from, onAdd }: { from: number | null; onAdd: (ramp: { kg: number; reps: number }[]) => void }) {
  const [target, setTarget] = useState(from ? String(from) : '')
  const [count, setCount] = useState(3)
  const weight = parseFloat(target.replace(',', '.'))
  const ramp = weight > 0 ? rampSets(weight, count) : []
  const step = 'h-11 w-11 rounded-[10px] text-[22px] font-semibold disabled:opacity-30'
  return (
    <div className="flex h-full flex-col gap-2.5 rounded-2xl bg-muted p-3">
      <div className="grid grid-cols-2 gap-2.5">
        <label className="flex flex-col gap-1 text-xs font-semibold text-muted-foreground">
          Working weight
          <span className="flex h-12 items-center gap-1.5 rounded-xl bg-card px-3">
            <input inputMode="decimal" value={target} onChange={(e) => setTarget(e.target.value)} placeholder="0"
              className="w-full bg-transparent font-mono text-lg font-semibold text-foreground outline-none" />
            <span className="text-sm font-normal">kg</span>
          </span>
        </label>
        <div className="flex flex-col gap-1 text-xs font-semibold text-muted-foreground">
          Warm-up sets
          <span className="flex h-12 items-center justify-between rounded-xl bg-card px-0.5 text-foreground">
            <button type="button" aria-label="Fewer sets" disabled={count <= 1} onClick={() => setCount(count - 1)} className={step}>−</button>
            <span className="font-mono text-lg">{count}</span>
            <button type="button" aria-label="More sets" disabled={count >= MAX_RAMP} onClick={() => setCount(count + 1)} className={step}>+</button>
          </span>
        </div>
      </div>
      <div className="-mr-3 flex min-h-9 items-center gap-2 overflow-x-auto pr-3">
        {ramp.length ? (
          ramp.map((r, i) => (
            <span key={i} className="shrink-0 rounded-lg bg-card px-2.5 py-1.5 font-mono text-sm font-semibold">{kg(r.kg)} kg</span>
          ))
        ) : (
          <span className="text-sm text-muted-foreground">Type your working weight to see the ramp</span>
        )}
      </div>
      <button type="button" disabled={!ramp.length} onClick={() => onAdd(ramp)}
        className="mt-auto h-12 rounded-[14px] bg-primary font-semibold text-primary-foreground disabled:opacity-40">
        Add
      </button>
    </div>
  )
}
