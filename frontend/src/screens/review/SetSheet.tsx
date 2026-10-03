import { useState } from 'react'
import Sheet from '@/components/Sheet'
import { RPES, stepReps, stepWeight, type SetDraft, type SetKind } from '@/lib/review'

const STEP = 'h-14 rounded-2xl border border-border bg-background font-mono text-[15px] font-semibold active:scale-95 transition-transform'
const BIG_INPUT =
  'h-13 w-24 border-0 border-b-[1.5px] border-border bg-transparent text-center font-mono text-[30px] font-semibold focus:border-foreground focus:outline-none'

/** Edits one set: weight, reps, RPE, warmup or working, note. Nothing is sent until Done. */
export default function SetSheet({
  title,
  initial,
  busy,
  error,
  onDone,
  onDelete,
  onClose,
}: {
  title: string
  initial: SetDraft
  busy: boolean
  error: string | null
  onDone: (draft: SetDraft) => void
  onDelete: () => void
  onClose: () => void
}) {
  const [draft, setDraft] = useState(initial)
  const set = (patch: Partial<SetDraft>) => setDraft((d) => ({ ...d, ...patch }))
  const repsStep = (delta: number) => {
    const next = stepReps(draft.reps, delta)
    if (next != null) set({ reps: next })
  }

  return (
    <Sheet open onClose={onClose} label="Edit set">
      <div className="flex items-center justify-between gap-3">
        <span className="min-w-0 truncate text-[17px] font-semibold">{title}</span>
        <div role="group" aria-label="Set type" className="grid shrink-0 grid-cols-2 rounded-xl bg-background p-0.5">
          {(['warmup', 'working'] as SetKind[]).map((k) => (
            <button
              key={k}
              type="button"
              aria-pressed={draft.kind === k}
              onClick={() => set({ kind: k })}
              className={`h-9 rounded-[10px] px-3 text-[13px] font-semibold ${
                draft.kind === k ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground'
              }`}
            >
              {k === 'warmup' ? 'Warmup' : 'Working'}
            </button>
          ))}
        </div>
      </div>

      <Stepper id="weight" label="Weight, 0 for bodyweight" unit="kg" value={draft.weight} inputMode="decimal"
        onChange={(v) => set({ weight: v })}
        minus={{ text: '−2.5', label: 'Minus 2.5 kg', run: () => set({ weight: stepWeight(draft.weight, -2.5) }) }}
        plus={{ text: '+2.5', label: 'Plus 2.5 kg', run: () => set({ weight: stepWeight(draft.weight, 2.5) }) }}
      />
      <Stepper id="reps" label="Reps" unit="reps" value={draft.reps} inputMode="text"
        onChange={(v) => set({ reps: v })}
        minus={{ text: '−1', label: 'Minus 1 rep', run: () => repsStep(-1) }}
        plus={{ text: '+1', label: 'Plus 1 rep', run: () => repsStep(1) }}
      />

      {draft.kind === 'working' && (
        <div className="flex flex-col gap-1.5">
          <span className="text-[13px] font-semibold">
            RPE <span className="font-normal text-muted-foreground">· optional, how hard it was out of 10</span>
          </span>
          <div role="group" aria-label="RPE" className="-mx-5 flex gap-1.5 overflow-x-auto px-5 pb-0.5">
            {[null, ...RPES].map((r) => (
              <button
                key={r ?? 'none'}
                type="button"
                aria-pressed={draft.rpe === r}
                onClick={() => set({ rpe: r })}
                className={`h-11 min-w-12 shrink-0 rounded-xl border px-2.5 font-mono text-sm font-semibold ${
                  draft.rpe === r
                    ? 'border-primary bg-primary text-primary-foreground'
                    : 'border-border bg-card text-foreground'
                }`}
              >
                {r ?? 'None'}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        <label htmlFor="set-note" className="text-[13px] font-semibold">
          Note
        </label>
        <input
          id="set-note"
          value={draft.note}
          onChange={(e) => set({ note: e.target.value })}
          placeholder="Felt easy, hip lifted, failed rep 3"
          className="h-11 rounded-xl border border-border bg-background px-3"
        />
      </div>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="flex gap-2.5">
        <button
          type="button"
          disabled={busy}
          onClick={onDelete}
          className="h-13 rounded-2xl border border-destructive/40 px-4 font-semibold text-destructive disabled:opacity-50"
        >
          Delete set
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => onDone(draft)}
          className="h-13 flex-1 rounded-2xl bg-primary font-semibold text-primary-foreground disabled:opacity-50"
        >
          {busy ? 'Saving…' : 'Done'}
        </button>
      </div>
    </Sheet>
  )
}

function Stepper(props: {
  id: string
  label: string
  unit: string
  value: string
  inputMode: 'decimal' | 'text'
  onChange: (value: string) => void
  minus: { text: string; label: string; run: () => void }
  plus: { text: string; label: string; run: () => void }
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={props.id} className="text-[13px] font-semibold">
        {props.label}
      </label>
      <div className="grid grid-cols-[72px_minmax(0,1fr)_72px] items-center gap-2.5">
        <button type="button" aria-label={props.minus.label} onClick={props.minus.run} className={STEP}>
          {props.minus.text}
        </button>
        <div className="flex items-baseline justify-center gap-1.5">
          <input
            id={props.id}
            inputMode={props.inputMode}
            value={props.value}
            onChange={(e) => props.onChange(e.target.value)}
            className={BIG_INPUT}
          />
          <span className="text-sm text-muted-foreground">{props.unit}</span>
        </div>
        <button type="button" aria-label={props.plus.label} onClick={props.plus.run} className={STEP}>
          {props.plus.text}
        </button>
      </div>
    </div>
  )
}
