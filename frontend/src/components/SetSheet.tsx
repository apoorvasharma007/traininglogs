import { useState } from 'react'
import Sheet from '@/components/Sheet'
import { EFFORT_FILL, EFFORTS, effortLevel } from '@/lib/effort'
import { kg } from '@/lib/format'
import { RPES, type SetDraft, type SetKind } from '@/lib/review'
import { rampSets } from '@/lib/session'

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
      <div className="flex items-center justify-between gap-3">
        <span className="flex min-w-0 flex-col">
          <span className="truncate text-[17px] font-semibold">{title}</span>
          {last && <span className="text-xs text-muted-foreground">Last time {last}</span>}
        </span>
        <div role="group" aria-label="Set type" className="grid shrink-0 grid-cols-2 rounded-xl bg-muted p-0.5">
          {(['warmup', 'working'] as SetKind[]).map((k) => (
            <button key={k} type="button" aria-pressed={draft.kind === k} onClick={() => set({ kind: k })}
              className={`h-9 rounded-[10px] px-3 text-[13px] font-semibold ${
                draft.kind === k ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground'
              }`}>
              {k === 'warmup' ? 'Warm-up' : 'Working'}
            </button>
          ))}
        </div>
      </div>

      {draft.kind === 'warmup' &&
        (onRamp ? (
          <RampUp from={rampFrom} onAdd={onRamp} />
        ) : (
          // Keeps the drawer the same height as a working set's, so the switch doesn't jump under your finger.
          <div className="flex h-[5.75rem] items-center justify-center rounded-xl bg-muted/50 text-sm text-muted-foreground">
            Warm-up sets don't track effort
          </div>
        ))}
      {draft.kind === 'working' && (
        // Each word, with the RPE numbers it covers under it: tap the word for its usual number, or
        // a number to be exact. Tapping the chosen one again clears it.
        <div role="group" aria-label="Effort" className="grid min-h-[5.75rem] grid-cols-3 gap-1.5">
          {EFFORTS.map((e) => {
            const on = effortLevel(draft.rpe) === e.level
            return (
              <div key={e.level} className="flex flex-col gap-1">
                <button type="button" aria-pressed={on} onClick={() => set({ rpe: on ? null : e.rpe })}
                  className={`flex h-14 flex-col items-center justify-center rounded-xl transition-colors ${on ? EFFORT_FILL[e.level] : 'bg-muted text-foreground'}`}>
                  <span className="text-[15px] font-semibold">{e.label}</span>
                  <span className={`text-[11px] ${on ? 'opacity-80' : 'text-muted-foreground'}`}>{e.means}</span>
                </button>
                <div className="flex gap-0.5">
                  {RPES.filter((r) => effortLevel(r) === e.level).map((r) => (
                    <button key={r} type="button" aria-pressed={draft.rpe === r} aria-label={`RPE ${r}`}
                      onClick={() => set({ rpe: draft.rpe === r ? null : r })}
                      className={`h-8 min-w-0 flex-1 rounded-md font-mono text-[12px] font-semibold ${
                        draft.rpe === r ? EFFORT_FILL[e.level] : 'text-muted-foreground'
                      }`}>
                      {r}
                    </button>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}

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
          Remove set
        </button>
        <button type="button" disabled={busy} onClick={() => onDone(draft)}
          className="h-12 min-w-32 rounded-2xl bg-primary px-6 font-semibold text-primary-foreground transition active:scale-[0.98] disabled:opacity-50">
          {busy ? 'Saving…' : 'Done'}
        </button>
      </div>
    </>
  )
}

/** A ramp of warm-up sets up to a target weight, added to the set's exercise in one tap. */
function RampUp({ from, onAdd }: { from: number | null; onAdd: (ramp: { kg: number; reps: number }[]) => void }) {
  const [target, setTarget] = useState(from ? String(from) : '')
  const [count, setCount] = useState('3')
  const weight = parseFloat(target.replace(',', '.'))
  const ramp = weight > 0 ? rampSets(weight, parseInt(count, 10)) : []
  const box = 'h-10 rounded-xl bg-muted text-center font-mono text-[15px]'
  return (
    <div className="flex min-h-[5.75rem] flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2 text-[15px]">
        <span>Ramp up to</span>
        <input aria-label="Target weight" inputMode="decimal" value={target} onChange={(e) => setTarget(e.target.value)}
          className={`${box} w-20`} />
        <span>kg in</span>
        <input aria-label="Warm-up sets" inputMode="numeric" value={count} maxLength={1}
          onChange={(e) => setCount(e.target.value.replace(/\D/g, ''))} className={`${box} w-11`} />
        <span>sets</span>
      </div>
      <button type="button" disabled={!ramp.length} onClick={() => onAdd(ramp)}
        className="flex min-h-12 items-center gap-3 rounded-xl bg-muted py-1.5 pr-1.5 pl-3.5 text-left disabled:opacity-60">
        <span className="flex min-w-0 flex-1 flex-wrap gap-x-4 font-mono text-[13px]">
          {ramp.length
            ? ramp.map((r, i) => <span key={i}>{kg(r.kg)} × {r.reps}</span>)
            : <span className="font-sans text-muted-foreground">{weight > 0 ? 'Pick 1 to 5 sets' : 'Type a weight to see the ramp'}</span>}
        </span>
        <span className="rounded-lg bg-primary px-3.5 py-2 text-sm font-semibold text-primary-foreground">Add</span>
      </button>
    </div>
  )
}
