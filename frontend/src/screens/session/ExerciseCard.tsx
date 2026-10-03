import { Check, ChevronDown, Clock, Ellipsis, Pin } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import NumberBox from '@/components/NumberBox'
import type { LiveExercise, LiveSet } from '@/lib/session'

/** One exercise in the session: pinned and last-time notes, today's note, and its sets. */
export default function ExerciseCard({
  exercise,
  pinned,
  onOpenSet,
  onValue,
  onTick,
  onAddSet,
  onMenu,
  onRename,
  onNote,
  onTogglePin,
}: {
  exercise: LiveExercise
  pinned: string | null
  onOpenSet: (set: LiveSet) => void
  onValue: (set: LiveSet, field: 'weight' | 'reps', value: string) => void
  onTick: (set: LiveSet) => void
  onAddSet: () => void
  onMenu: () => void
  onRename: (name: string) => void
  onNote: (note: string) => void
  onTogglePin: () => void
}) {
  const e = exercise
  // Warmup sets show "W"; working sets are numbered 1, 2, 3.
  const labels = e.sets.map((x, i) =>
    x.kind === 'warmup' ? 'W' : String(e.sets.slice(0, i + 1).filter((y) => y.kind === 'working').length),
  )
  const isPinned = pinned != null && e.note.trim() !== '' && pinned === e.note.trim()

  return (
    <section className="overflow-hidden rounded-2xl border border-border bg-card">
      <div className="flex items-start justify-between pt-2.5 pr-1 pb-1 pl-4">
        <div className="flex min-w-0 flex-col gap-1 pt-1">
          {e.naming ? (
            <NameField initial={e.name} onCommit={onRename} />
          ) : (
            <h2 className="text-base font-semibold">{e.name}</h2>
          )}
          {pinned && (
            <p className="flex items-start gap-1.5 text-xs leading-snug text-foreground/80">
              <Pin size={13} aria-label="Pinned note" className="mt-0.5 shrink-0" />
              <span>{pinned}</span>
            </p>
          )}
          {e.lastNote && (
            <p className="flex items-start gap-1.5 text-xs leading-snug text-faint-foreground">
              <Clock size={13} aria-label="Last time" className="mt-0.5 shrink-0" />
              <span>{e.lastNote}</span>
            </p>
          )}
        </div>
        <button type="button" aria-label={`Options for ${e.name || 'new exercise'}`} onClick={onMenu}
          className="flex size-11 shrink-0 items-center justify-center text-muted-foreground">
          <Ellipsis size={20} aria-hidden />
        </button>
      </div>

      {(e.noteOpen || e.note) && (
        <div className="flex items-center gap-1.5 px-4 pb-2.5">
          <label htmlFor={`note-${e.key}`} className="sr-only">
            Note for today
          </label>
          <input id={`note-${e.key}`} autoFocus={e.noteOpen && !e.note} value={e.note} placeholder="Note for today"
            onChange={(ev) => onNote(ev.target.value)}
            className="h-11 min-w-0 flex-1 rounded-xl border border-muted-foreground/60 bg-card px-3 text-sm" />
          <button type="button" aria-pressed={isPinned} disabled={!e.note.trim()} onClick={onTogglePin}
            aria-label={isPinned ? 'Unpin this note' : 'Pin this note to every session'}
            className={`flex size-11 shrink-0 items-center justify-center rounded-xl border transition active:scale-90 disabled:opacity-40 ${
              isPinned ? 'border-primary bg-primary text-primary-foreground' : 'border-border text-muted-foreground'
            }`}>
            <Pin size={18} aria-hidden />
          </button>
        </div>
      )}

      <div className="grid grid-cols-[44px_64px_minmax(0,1fr)_minmax(0,1fr)_48px] items-center gap-1.5 pl-3 text-[11px] font-semibold tracking-wide text-faint-foreground">
        <span className="pl-1">SET</span>
        <span>LAST</span>
        <span className="text-center">KG</span>
        <span className="text-center">REPS</span>
        <span className="text-center">DONE</span>
      </div>

      <AnimatePresence initial={false}>
        {e.sets.map((set, i) => {
          const warm = set.kind === 'warmup'
          const label = labels[i]
          return (
            <motion.div key={set.key} layout initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.18 }}
              className={`grid min-h-13 grid-cols-[44px_64px_minmax(0,1fr)_minmax(0,1fr)_48px] items-center gap-1.5 border-t border-border pl-3 transition-colors ${
                set.done ? 'bg-highlight-soft' : ''
              }`}>
              <button type="button" onClick={() => onOpenSet(set)} aria-label={`Set ${label} options`}
                className={`flex h-10 items-center justify-center gap-0.5 rounded-lg font-mono text-[13px] font-semibold transition active:scale-95 ${
                  warm ? 'text-warning' : 'text-muted-foreground'
                }`}>
                {label}
                <ChevronDown size={12} strokeWidth={2.5} aria-hidden className="opacity-60" />
              </button>
              <span className="truncate font-mono text-xs text-faint-foreground">
                {set.last ?? '—'}
                {set.rpe != null && <span className="block text-[10px] text-muted-foreground">RPE {set.rpe}</span>}
              </span>
              <NumberBox label={`Weight for set ${label}`} done={set.done}
                value={set.ghost ? '' : set.weight} placeholder={set.ghost && set.weight ? set.weight : 'kg'}
                onChange={(v) => onValue(set, 'weight', v)} />
              <NumberBox label={`Reps for set ${label}`} inputMode="numeric" done={set.done}
                value={set.ghost ? '' : set.reps} placeholder={set.ghost && set.reps ? set.reps : 'reps'}
                onChange={(v) => onValue(set, 'reps', v)} />
              <button type="button" onClick={() => onTick(set)} aria-label={`Set ${label} done`} aria-pressed={set.done}
                className="flex size-12 items-center justify-center">
                <motion.span key={String(set.done)} initial={{ scale: set.done ? 0.6 : 1 }} animate={{ scale: 1 }}
                  transition={{ type: 'spring', stiffness: 520, damping: 14 }}
                  className={`flex size-7 items-center justify-center rounded-lg border-[1.5px] ${
                    set.done ? 'border-highlight bg-highlight text-background' : 'border-border text-transparent'
                  }`}>
                  <Check size={16} strokeWidth={3} aria-hidden />
                </motion.span>
              </button>
            </motion.div>
          )
        })}
      </AnimatePresence>

      <div className="border-t border-border px-3 pt-2 pb-3">
        <button type="button" onClick={onAddSet}
          className="h-10 rounded-xl border border-dashed border-muted-foreground/50 px-3.5 text-[13px] font-semibold text-muted-foreground transition active:scale-95">
          + Set
        </button>
      </div>
    </section>
  )
}

function NameField({ initial, onCommit }: { initial: string; onCommit: (name: string) => void }) {
  const [name, setName] = useState(initial)
  return (
    <>
      <label htmlFor="new-exercise-name" className="sr-only">
        Exercise name
      </label>
      <input id="new-exercise-name" autoFocus value={name} placeholder="Exercise name"
        onChange={(e) => setName(e.target.value)}
        onBlur={() => name.trim() && onCommit(name.trim())}
        onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
        className="h-10 w-56 rounded-xl border border-muted-foreground/60 bg-card px-3 text-base font-semibold" />
    </>
  )
}
