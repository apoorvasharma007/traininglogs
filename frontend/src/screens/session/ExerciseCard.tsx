import { ArrowLeftRight, Check, ChevronDown, Clock, Ellipsis, MessageSquareText } from 'lucide-react'
import { Chevron } from '@/components/Collapse'
import { AnimatePresence, motion } from 'motion/react'
import { type FocusEvent, useState } from 'react'
import EffortBars from '@/components/EffortBars'
import NoteBox from '@/components/NoteBox'
import NumberBox from '@/components/NumberBox'
import type { LiveExercise, LiveSet } from '@/lib/session'
import ColumnHead from '@/components/ColumnHead'
import { BTN } from '@/lib/ui'

/** A box still showing last time's number (or a suggestion) in grey. */
const grey = (set: LiveSet, field: 'weight' | 'reps') => set.ghost && set.own !== field

/** One exercise in the session: last time's note, today's note, and its sets. */
export default function ExerciseCard({
  exercise,
  onOpenSet,
  onValue,
  onTick,
  onEntered,
  onAddSet,
  onMenu,
  onRename,
  onSwitch,
  collapsed,
  onToggleCollapsed,
  onNote,
}: {
  exercise: LiveExercise
  onOpenSet: (set: LiveSet) => void
  onValue: (set: LiveSet, field: 'weight' | 'reps', value: string) => void
  onTick: (set: LiveSet) => void
  /** Weight or reps typed and the keyboard left the set's row. */
  onEntered: (set: LiveSet) => void
  onAddSet: () => void
  onMenu: () => void
  onRename: (name: string) => void
  onSwitch: () => void
  /** Shown as one line: folded by hand, or all sets ticked and not opened again. */
  collapsed: boolean
  onToggleCollapsed: () => void
  onNote: (note: string) => void
}) {
  const e = exercise
  const doneCount = e.sets.filter((x) => x.done).length
  const allDone = e.sets.length > 0 && doneCount === e.sets.length
  // Warmup sets show "W"; working sets are numbered 1, 2, 3.
  const labels = e.sets.map((x, i) =>
    x.kind === 'warmup' ? 'W' : String(e.sets.slice(0, i + 1).filter((y) => y.kind === 'working').length),
  )

  return (
    <section id={`ex-${e.key}`} className="scroll-mt-28 overflow-hidden rounded-2xl border border-border bg-card">
      {collapsed ? (
        <button type="button" onClick={onToggleCollapsed} aria-expanded={false}
          aria-label={allDone
            ? `${e.name}: all ${e.sets.length} ${e.sets.length === 1 ? 'set' : 'sets'} done. Show sets`
            : `${e.name || 'Exercise'}: ${doneCount} of ${e.sets.length} sets done. Show sets`}
          className="flex min-h-13 w-full items-center gap-3 px-4 text-left">
          <span className={`flex size-6 shrink-0 items-center justify-center rounded-full ${
            allDone ? 'bg-highlight text-background' : 'border-[1.5px] border-border text-transparent'
          }`}>
            <Check size={14} strokeWidth={3} aria-hidden />
          </span>
          <span className="min-w-0 flex-1 truncate text-[15px] font-semibold">{e.name || 'Exercise'}</span>
          <span className="shrink-0 text-[13px] text-muted-foreground">{doneCount} of {e.sets.length} sets</span>
          <Chevron open={false} className="text-faint-foreground" />
        </button>
      ) : (
        <div className="flex items-start justify-between pt-2.5 pr-1 pb-1 pl-4">
          <div className="flex min-w-0 flex-col gap-1 pt-1">
            {e.naming ? (
              <NameField initial={e.name} choices={e.choices} onCommit={onRename} />
            ) : (
              <h2 className="flex items-center gap-1.5 text-base font-semibold">
                {e.name}
                {e.choices.length > 1 && (
                  <button type="button" onClick={onSwitch} aria-label={`Switch ${e.name} to an alternative`}
                    className="-m-2 flex size-9 items-center justify-center text-muted-foreground active:scale-90">
                    <ArrowLeftRight size={14} aria-hidden />
                  </button>
                )}
              </h2>
            )}
            {e.lastNote && (
              <p className="flex items-start gap-1.5 text-[13px] leading-snug text-faint-foreground">
                <Clock size={14} aria-label="Last time" className="mt-0.5 shrink-0" />
                <span>{e.lastNote}</span>
              </p>
            )}
          </div>
          <div className="flex shrink-0">
            <button type="button" onClick={onToggleCollapsed} aria-expanded aria-label={`Hide sets of ${e.name || 'exercise'}`}
              className="flex size-11 items-center justify-center text-muted-foreground">
              <Chevron open size={22} />
            </button>
            <button type="button" aria-label={`Options for ${e.name || 'new exercise'}`} onClick={onMenu}
              className="flex size-11 items-center justify-center text-muted-foreground">
              <Ellipsis size={22} aria-hidden />
            </button>
          </div>
        </div>
      )}

      <AnimatePresence initial={false}>
        {!collapsed && (
          <motion.div key="sets" initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.24, ease: [0.32, 0.72, 0, 1] }} className="overflow-hidden">
            {(e.noteOpen || e.note) && (
              <div className="flex items-center gap-1.5 px-4 pb-2.5">
                <label htmlFor={`note-${e.key}`} className="sr-only">
                  Note for today
                </label>
                <NoteBox id={`note-${e.key}`} autoFocus={e.noteOpen && !e.note} value={e.note} placeholder="Note for today"
                  onChange={(ev) => onNote(ev.target.value)}
                  className="min-h-11 min-w-0 flex-1 rounded-xl border border-muted-foreground/60 bg-card px-3 text-[15px]" />
              </div>
            )}

            <ColumnHead className="grid-cols-[56px_minmax(0,1fr)_minmax(0,1fr)_48px] pl-3">
              <span className="pl-1">SET</span>
              <span className="text-center">KG</span>
              <span className="text-center">REPS</span>
              <span className="text-center">DONE</span>
            </ColumnHead>

            <AnimatePresence initial={false}>
              {e.sets.map((set, i) => {
                const warm = set.kind === 'warmup'
                const label = labels[i]
                // Moving between this set's two boxes isn't leaving it.
                const leave = (ev: FocusEvent<HTMLInputElement>) => {
                  if (!ev.currentTarget.closest('[data-set]')?.contains(ev.relatedTarget as Node | null)) onEntered(set)
                }
                return (
                  <motion.div key={set.key} layout initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.18 }}
                    data-set=""
                    className={`grid min-h-13 grid-cols-[56px_minmax(0,1fr)_minmax(0,1fr)_48px] items-center gap-1.5 pl-3 transition-colors ${
                      set.done ? 'bg-highlight-soft' : ''
                    }`}>
                    <button type="button" onClick={() => onOpenSet(set)} aria-label={`Set ${label} options`}
                      className={`flex h-10 items-center justify-center gap-1 rounded-lg font-mono text-[13px] font-semibold transition active:scale-95 ${
                        warm ? 'text-warning' : 'text-muted-foreground'
                      }`}>
                      {label}
                      <EffortBars rpe={set.rpe} />
                      {set.note && <MessageSquareText size={14} strokeWidth={2.2} aria-label="has a note" className="text-foreground" />}
                      {!set.note && set.rpe == null && <ChevronDown size={14} strokeWidth={2.5} aria-hidden className="opacity-60" />}
                    </button>
                    <NumberBox label={`Weight for set ${label}`} done={set.done}
                      value={grey(set, 'weight') ? '' : set.weight} placeholder={grey(set, 'weight') && set.weight ? set.weight : 'kg'} fillable={grey(set, 'weight') && !!set.weight}
                      onChange={(v) => onValue(set, 'weight', v)} onBlur={leave} />
                    <NumberBox label={`Reps for set ${label}`} inputMode="numeric" done={set.done}
                      value={grey(set, 'reps') ? '' : set.reps} placeholder={grey(set, 'reps') && set.reps ? set.reps : 'reps'} fillable={grey(set, 'reps') && !!set.reps}
                      onChange={(v) => onValue(set, 'reps', v)} onBlur={leave} />
                    <button type="button" onClick={() => onTick(set)} aria-label={`Set ${label} done`} aria-pressed={set.done}
                      className="flex size-12 items-center justify-center">
                      <motion.span key={String(set.done)} initial={{ scale: set.done ? 0.6 : 1 }} animate={{ scale: 1 }}
                        transition={{ type: 'spring', stiffness: 520, damping: 14 }}
                        className={`flex size-7 items-center justify-center rounded-lg border-[1.5px] ${
                          set.done ? 'border-highlight bg-highlight text-background' : 'border-border text-transparent'
                        }`}>
                        <Check size={18} strokeWidth={3} aria-hidden />
                      </motion.span>
                    </button>
                  </motion.div>
                )
              })}
            </AnimatePresence>

            <div className="px-3 pt-2 pb-3">
              <button type="button" onClick={onAddSet}
                className={BTN.smallSecondary}>
                + Set
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}

/** The exercise's name, typed; the plan line's other choices are offered while typing. */
function NameField({ initial, choices, onCommit }: { initial: string; choices: string[]; onCommit: (name: string) => void }) {
  const [name, setName] = useState(initial)
  return (
    <>
      <datalist id="exercise-choices">
        {choices.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>
      <label htmlFor="new-exercise-name" className="sr-only">
        Exercise name
      </label>
      <input id="new-exercise-name" list="exercise-choices" autoFocus autoCapitalize="words" value={name} placeholder="Exercise name"
        onChange={(e) => setName(e.target.value)}
        onBlur={() => name.trim() && onCommit(name.trim())}
        onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
        className="h-10 w-56 rounded-xl border border-muted-foreground/60 bg-card px-3 text-base font-semibold" />
    </>
  )
}
