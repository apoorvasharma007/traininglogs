import { useState } from 'react'
import Sheet from '@/components/Sheet'
import { EFFORTS, effortLevel } from '@/lib/effort'
import { RPES, type SetDraft, type SetKind } from '@/lib/review'


export type SetTarget = { key: string; title: string; draft: SetDraft; last?: string | null }

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
}: {
  target: SetTarget | null
  busy: boolean
  error: string | null
  onDone: (draft: SetDraft) => void
  onDelete: () => void
  onClose: () => void
}) {
  // Keeps showing the last set while the drawer slides away.
  const [shown, setShown] = useState(target)
  if (target && target !== shown) setShown(target)
  return (
    <Sheet open={target != null} onClose={onClose} label="Edit set">
      {shown && (
        <SetForm key={shown.key} title={shown.title} last={shown.last ?? null} initial={shown.draft} busy={busy} error={error}
          onDone={onDone} onDelete={onDelete} />
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
}: {
  title: string
  last: string | null
  initial: SetDraft
  busy: boolean
  error: string | null
  onDone: (draft: SetDraft) => void
  onDelete: () => void
}) {
  const level = effortLevel(initial.rpe)
  // An RPE that isn't one of the three words' own numbers opens the exact row straight away.
  const [exact, setExact] = useState(initial.rpe != null && !EFFORTS.some((e) => e.rpe === initial.rpe) && level > 0)
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

      {draft.kind === 'warmup' && (
        // Keeps the drawer the same height as a working set's, so the switch doesn't jump under your finger.
        <div className="flex h-[5.75rem] items-center justify-center rounded-xl bg-muted/50 text-sm text-muted-foreground">
          Warm-up sets don't track effort
        </div>
      )}
      {draft.kind === 'working' && (
        <div className="flex min-h-[5.75rem] flex-col gap-2">
          <div role="group" aria-label="Effort" className="grid grid-cols-3 gap-1.5">
            {EFFORTS.map((e) => {
              const on = effortLevel(draft.rpe) === e.level
              return (
                <button key={e.level} type="button" aria-pressed={on}
                  // Tapping the chosen word again clears the effort.
                  onClick={() => set({ rpe: on ? null : e.rpe })}
                  className={`flex h-14 flex-col items-center justify-center rounded-xl transition-colors ${
                    on ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground'
                  }`}>
                  <span className="text-[15px] font-semibold">{e.label}</span>
                  <span className={`text-[11px] ${on ? 'opacity-80' : 'text-muted-foreground'}`}>{e.means}</span>
                </button>
              )
            })}
          </div>
          {exact ? (
            <div role="group" aria-label="RPE" className="-mr-5 flex gap-1 overflow-x-auto pr-5 pb-0.5">
              {RPES.map((r) => (
                <button key={r} type="button" aria-pressed={draft.rpe === r} aria-label={`RPE ${r}`}
                  onClick={() => set({ rpe: draft.rpe === r ? null : r })}
                  className={`h-9 min-w-10 shrink-0 rounded-lg px-2 font-mono text-[13px] font-semibold ${
                    draft.rpe === r ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground'
                  }`}>
                  {r}
                </button>
              ))}
            </div>
          ) : (
            <button type="button" onClick={() => setExact(true)} className="self-start px-1 text-[13px] font-semibold text-muted-foreground">
              Exact RPE
            </button>
          )}
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
