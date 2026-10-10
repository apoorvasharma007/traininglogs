import { useQueryClient } from '@tanstack/react-query'
import Parts from '@/components/Parts'
import { ArrowUpDown, ChevronDown, Flame, MessageSquareText, Pencil, Trash2, X } from 'lucide-react'
import { MotionConfig } from 'motion/react'
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'wouter'
import ConfirmSheet from '@/components/ConfirmSheet'
import UndoBar from '@/components/UndoBar'
import DragList from '@/components/DragList'
import { Loading } from '@/components/QueryStatus'
import SetSheet, { type SetTarget } from '@/components/SetSheet'
import EffortSheet, { type EffortTarget } from '@/components/EffortSheet'
import Sheet from '@/components/Sheet'
import { api } from '@/lib/api'
import { planChanges } from '@/lib/planChanges'
import { COOLDOWN_PRESETS, WARMUP_PRESETS } from '@/lib/movements'
import { WARMUPS, warmupSets } from '@/lib/warmup'
import {
  addExercise,
  addSet,
  addRamp,
  setEffort,
  liveTitle,
  counts,
  draftOf,
  reorderExercises,
  removeExercise,
  removeSet,
  saveSet,
  setValue,
  setWarmups,
  wantsWarmupNudge,
  recordCardio,
  CARDIO_MINUTES,
  setMovements,
  movementsOf,
  addPreset,
  switchExercise,
  toRequest,
  toggleDone,
  updateExercise,
  type LiveExercise,
  type LiveSet,
  type LiveSession,
} from '@/lib/session'
import { enqueue, flush, useLiveSession } from '@/lib/store'
import { setLastFinished } from '@/screens/session/finished'
import type { Program } from '@/lib/types'
import ExerciseCard from './ExerciseCard'
import MovementCard from './MovementCard'
import { BTN, SHEET_TITLE } from '@/lib/ui'
import { cn } from '@/lib/utils'
import { MenuGroup, MenuItem } from '@/components/Menu'

function minutesSince(iso: string, now: number): number {
  return Math.max(0, Math.floor((now - new Date(iso).getTime()) / 60000))
}

/** The session in progress, full screen. Every change is saved on the phone straight away. */
export default function Session() {
  const { session, update } = useLiveSession()
  const [, navigate] = useLocation()
  const queryClient = useQueryClient()
  const [openSet, setOpenSet] = useState<(SetTarget & { exKey: string }) | null>(null)
  const [menuFor, setMenuFor] = useState<LiveExercise | null>(null)
  const [switchFor, setSwitchFor] = useState<LiveExercise | null>(null)
  const [warmupFor, setWarmupFor] = useState<LiveExercise | null>(null)
  const [reordering, setReordering] = useState(false)
  // Finished exercises collapse; these were opened again by hand.
  const [reopened, setReopened] = useState<Set<string>>(() => new Set())
  // Any exercise can be folded by hand, finished or not, to keep the page short.
  const [folded, setFolded] = useState<Set<string>>(() => new Set())
  // The working set just ticked, asked how hard it was.
  const [effortFor, setEffortFor] = useState<EffortTarget | null>(null)
  const [undo, setUndo] = useState<{ text: string; before: LiveSession; at: number } | null>(null)
  const [finishing, setFinishing] = useState(false)
  const [discarding, setDiscarding] = useState(false)
  const [finishError, setFinishError] = useState<string | null>(null)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 15_000)
    return () => clearInterval(id)
  }, [])

  if (session === undefined) return <Loading />
  if (session === null) {
    return (
      <div className="flex flex-col gap-3 pt-16 text-center">
        <p className="font-semibold">No Session in Progress</p>
        <Link href="/" className="font-semibold text-muted-foreground underline">
          Back to Train
        </Link>
      </div>
    )
  }

  const s = session
  const { done, total } = counts(s)
  const finished = (e: LiveExercise) => e.sets.length > 0 && e.sets.every((x) => x.done)
  const isCollapsed = (e: LiveExercise) => folded.has(e.key) || (finished(e) && !reopened.has(e.key))

  /** After an exercise's last set is ticked, bring the next unfinished one into view. */
  function scrollToNext(next: LiveSession, fromKey: string) {
    const ex = next.exercises.find((e) => e.key === fromKey)
    if (!ex || !finished(ex)) return
    const after = next.exercises.slice(next.exercises.indexOf(ex) + 1).find((e) => !finished(e))
    if (!after) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    requestAnimationFrame(() =>
      document.getElementById(`ex-${after.key}`)?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' }),
    )
  }
  const change = (next: LiveSession) => {
    setUndo(null)
    update(next)
  }
  const removeWithUndo = (next: LiveSession, text: string) => {
    update(next)
    setUndo({ text, before: s, at: Date.now() })
  }

  function tick(ex: LiveExercise, set: LiveSet) {
    if (!set.done) navigator.vibrate?.(10)
    const next = toggleDone(s, set.key)
    change(next)
    if (!set.done) {
      setReopened((r) => { const n = new Set(r); n.delete(ex.key); return n })
      scrollToNext(next, ex.key)
      if (set.kind === 'working') askEffort(ex, set)
    }
  }

  function askEffort(ex: LiveExercise, set: LiveSet) {
    const number = ex.sets.filter((x) => x.kind === 'working').findIndex((x) => x.key === set.key) + 1
    setEffortFor({
      setKey: set.key, set: String(number),
      did: set.weight && set.reps ? `${set.weight} kg × ${set.reps}` : '',
    })
  }

  function open(exKey: string, setKey: string, session: LiveSession = s) {
    const ex = session.exercises.find((e) => e.key === exKey)
    const index = ex?.sets.findIndex((x) => x.key === setKey) ?? -1
    if (!ex || index < 0) return
    const set = ex.sets[index]
    // Just the exercise: the Warm-up | Working switch already says which kind of set it is.
    const firstWorking = parseFloat(ex.sets.find((x) => x.kind === 'working')?.weight ?? '')
    setOpenSet({
      key: setKey, title: ex.name || 'Exercise', draft: draftOf(set), last: set.last, exKey,
      rampFrom: firstWorking > 0 ? firstWorking : null,
    })
  }

  async function finish() {
    const finishedAt = new Date()
    const request = toRequest(s, finishedAt)
    if (request.exercises.length === 0) {
      setFinishError("You haven't checked any sets. This workout session is empty.")
      return
    }
    // The plan to compare against: cached, or fetched; offline, there's simply nothing to offer.
    let program: Program | undefined
    if (s.programId) {
      const programId = s.programId
      program = queryClient.getQueryData<Program>(['program', programId])
        ?? (await queryClient.fetchQuery({ queryKey: ['program', programId], queryFn: () => api<Program>(`/programs/${programId}`) }).catch(() => undefined))
    }
    const workout = program?.workouts.find((w) => w.id === s.workoutId) ?? null
    setLastFinished({
      clientId: s.clientId,
      title: liveTitle(s),
      minutes: request.duration_minutes,
      sets: request.exercises.reduce((n, e) => n + e.sets.length + e.warmup_sets.length, 0),
      programId: s.programId,
      workoutId: s.workoutId,
      workout,
      changes: workout ? planChanges(s, workout) : [],
    })
    enqueue(request).then(() => {
      update(null)
      flush().finally(() => {
        queryClient.invalidateQueries({ queryKey: ['sessions'] })
        queryClient.invalidateQueries({ queryKey: ['programs'] })
        queryClient.invalidateQueries({ queryKey: ['lifts'] })
        if (s.programId) queryClient.invalidateQueries({ queryKey: ['program', s.programId] })
      })
      navigate('/session/done')
    })
  }

  return (
    <MotionConfig reducedMotion="user">
      <div className="pb-24">
        <header className="sticky top-0 z-10 -mx-4 mb-3 flex items-center gap-1 bg-muted/85 px-2 pt-3 pb-2 backdrop-blur-xl backdrop-saturate-150">
          <Link href="/" aria-label="Minimise; the session keeps going" className="flex size-11 shrink-0 items-center justify-center">
            <ChevronDown size={22} aria-hidden />
          </Link>
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="flex items-baseline gap-3 text-[17px] font-semibold">
              <span className="truncate">{liveTitle(s)}</span>
              <span className="shrink-0 font-normal text-muted-foreground">{minutesSince(s.startedAt, now)} min</span>
            </span>
          </div>
          <button type="button" onClick={() => { setFinishError(null); setFinishing(true) }}
            className={cn(BTN.smallPrimary, 'shrink-0')}>
            Finish
          </button>
        </header>


        <div className="flex flex-col gap-3">
          {wantsWarmupNudge(s) && <WarmupNudge session={s} onChange={change} />}
          <MovementCard title="Warm-up" movements={movementsOf(s, 'warmup')} presets={WARMUP_PRESETS}
            onChange={(list) => change(setMovements(s, 'warmup', list))}
            onAddPreset={(m) => change(addPreset(s, 'warmup', m))} />
          {s.exercises.map((ex) => (
            <ExerciseCard
              key={ex.key}
              exercise={ex}
              onOpenSet={(set) => open(ex.key, set.key)}
              onValue={(set, field, value) => change(setValue(s, set.key, field, value))}
              onTick={(set) => tick(ex, set)}
              onEntered={(set) => {
                // Both numbers typed and the keyboard gone: the set is done, no tick needed.
                if (!set.done && !set.ghost && set.weight && set.reps) tick(ex, set)
              }}
              collapsed={isCollapsed(ex)}
              onToggleCollapsed={() => {
                const opening = isCollapsed(ex)
                const toggle = (on: boolean) => (set: Set<string>) => {
                  const n = new Set(set)
                  if (on) n.add(ex.key)
                  else n.delete(ex.key)
                  return n
                }
                setFolded(toggle(!opening))
                setReopened(toggle(opening))
              }}
              onAddSet={() => change(addSet(s, ex.key).session)}
              onMenu={() => setMenuFor(ex)}
              onRename={(name) => change(updateExercise(s, ex.key, { name, naming: false }))}
              onSwitch={() => setSwitchFor(ex)}
              onNote={(note) => change(updateExercise(s, ex.key, { note }))}
            />
          ))}
          <button type="button" onClick={() => change(addExercise(s).session)}
            className={BTN.secondary}>
            + Exercise
          </button>
          <MovementCard title="Cool-down" movements={movementsOf(s, 'cooldown')} presets={COOLDOWN_PRESETS}
            onChange={(list) => change(setMovements(s, 'cooldown', list))}
            onAddPreset={(m) => change(addPreset(s, 'cooldown', m))} />
        </div>

        {undo && (
          <UndoBar key={undo.at} text={undo.text} className="bottom-6"
            onUndo={() => { update(undo.before); setUndo(null) }} onDismiss={() => setUndo(null)} />
        )}
      </div>

      <SetSheet target={openSet} busy={false} error={null}
        onClose={() => setOpenSet(null)}
        onDone={(draft) => { if (openSet) change(saveSet(s, openSet.key, draft)); setOpenSet(null) }}
        onDelete={() => { if (openSet) removeWithUndo(removeSet(s, openSet.key), 'Set removed'); setOpenSet(null) }}
        // Adds the sets without saving any change to the set the sheet was opened on.
        onRamp={(ramp) => { if (openSet) change(addRamp(s, openSet.exKey, ramp)); setOpenSet(null) }} />
      <EffortSheet target={effortFor} onClose={() => setEffortFor(null)}
        onPick={(setKey, rpe) => { change(setEffort(s, setKey, rpe)); setEffortFor(null) }} />

      <Sheet open={menuFor != null} onClose={() => setMenuFor(null)} label="Exercise Options">
        {menuFor && (
          <>
            <span className={SHEET_TITLE}>{menuFor.name || 'New Exercise'}</span>
            <MenuGroup>
              {s.exercises.length > 1 && (
                <MenuItem icon={ArrowUpDown} label="Reorder Exercises" onClick={() => { setMenuFor(null); setReordering(true) }} />
              )}
              <MenuItem icon={MessageSquareText} label={menuFor.note ? 'Edit Exercise Note' : 'Add Exercise Note'}
                onClick={() => { setMenuFor(null); change(updateExercise(s, menuFor.key, { noteOpen: true })) }} />
              <MenuItem icon={Pencil} label="Rename Exercise"
                onClick={() => { setMenuFor(null); change(updateExercise(s, menuFor.key, { naming: true })) }} />
              <MenuItem icon={Flame} label="Warm-up Set Templates" onClick={() => { setMenuFor(null); setWarmupFor(menuFor) }} />
            </MenuGroup>
            <MenuGroup danger>
              <MenuItem icon={Trash2} label="Remove Exercise" danger
                onClick={() => { setMenuFor(null); removeWithUndo(removeExercise(s, menuFor.key), `${menuFor.name || 'Exercise'} removed`) }} />
            </MenuGroup>
          </>
        )}
      </Sheet>

      <Sheet open={reordering} onClose={() => setReordering(false)} label="Reorder Exercises">
        <span className={SHEET_TITLE}>Reorder Exercises</span>
        <DragList items={s.exercises} keyOf={(e) => e.key} label={(e) => e.name || 'Exercise'}
          onReorder={(keys) => change(reorderExercises(s, keys))}>
          {(e) => <span className="flex h-14 items-center truncate px-4 text-[15px] font-medium">{e.name || 'Exercise'}</span>}
        </DragList>
        <button type="button" onClick={() => setReordering(false)}
          className={BTN.primary}>
          Done
        </button>
      </Sheet>

      <Sheet open={warmupFor != null} onClose={() => setWarmupFor(null)} label="Warm-up Set Templates">
        {warmupFor && <WarmupPicker exercise={warmupFor} onPick={(sets) => { change(setWarmups(s, warmupFor.key, sets)); setWarmupFor(null) }} />}
      </Sheet>

      <Sheet open={switchFor != null} onClose={() => setSwitchFor(null)} label="Alternatives">
        {switchFor && (
          <>
            <span className={SHEET_TITLE}>Alternatives</span>
            <MenuGroup>
              {switchFor.choices
                .filter((c) => c.trim().toLowerCase() !== switchFor.name.trim().toLowerCase())
                .map((c) => (
                  <MenuItem key={c} label={c} onClick={() => { change(switchExercise(s, switchFor.key, c)); setSwitchFor(null) }} />
                ))}
            </MenuGroup>
          </>
        )}
      </Sheet>

      <Sheet open={finishing} onClose={() => setFinishing(false)} label="Finish Session">
        <div className="flex flex-col gap-1.5">
          <span className={SHEET_TITLE}>Finish Session?</span>
          {/* Said only when something won't be saved. */}
          {done < total && (
            <p className="text-[15px] leading-snug text-muted-foreground">
              {done === 0
                ? "You haven't checked any sets. This workout session is empty."
                : `Only checked (green) sets are saved. You have ${total - done} unchecked ${total - done === 1 ? 'set' : 'sets'}.`}
            </p>
          )}
        </div>
        {finishError && <p role="alert" className="text-[15px] text-destructive">{finishError}</p>}
        {/* Nothing checked: the line above says so, and there's nothing to save. */}
        <button type="button" onClick={finish} disabled={done === 0} className={BTN.primary}>
          Save Session
        </button>
        <button type="button" onClick={() => setFinishing(false)} className={BTN.secondary}>
          Keep Going
        </button>
        <button type="button" onClick={() => { setFinishing(false); setDiscarding(true) }} className={BTN.danger}>
          Discard Session
        </button>
      </Sheet>

      <ConfirmSheet open={discarding} title="Discard This Session?"
        body={done > 0 ? `The ${done} ${done === 1 ? 'set' : 'sets'} you logged will be deleted.` : 'Nothing in it has been checked yet.'}
        confirmLabel="Discard Session" onClose={() => setDiscarding(false)}
        onConfirm={() => { update(null); navigate('/') }} />
    </MotionConfig>
  )
}

/** The warm-up ramps, each worked out from this exercise's first working weight. */
function WarmupPicker({ exercise, onPick }: { exercise: LiveExercise; onPick: (sets: { kg: number; reps: number }[]) => void }) {
  const working = parseFloat(exercise.sets.find((x) => x.kind === 'working')?.weight ?? '')
  // Any warm-up sets already here get replaced, including ones the program put there.
  const existing = exercise.sets.filter((x) => x.kind === 'warmup').length
  return (
    <>
      <div className="flex flex-col gap-0.5">
        <span className={SHEET_TITLE}>Warm-up Set Templates</span>
        <span className="text-[15px] text-muted-foreground">
          {working > 0
            ? `Builds up to your first working set, ${working} kg.`
            : 'Add a weight to your first working set. Warm-up templates are calculated from it.'}
        </span>
      </div>
      {working > 0 && existing > 0 && (
        <span className="text-[15px] text-warning">Replaces the {existing} warm-up {existing === 1 ? 'set' : 'sets'} already here.</span>
      )}
      <MenuGroup>
        {WARMUPS.map((w) => {
          // Without a working weight there's nothing to build toward: shown, but not tappable.
          const sets = working > 0 ? warmupSets(w.id, working) : []
          return (
            <MenuItem key={w.id} label={w.name} disabled={!(working > 0)} onClick={() => onPick(sets)}
              detail={sets.length > 0 && <Parts className="font-mono" items={sets.map((x) => `${x.kg}×${x.reps}`)} />} />
          )
        })}
      </MenuGroup>
    </>
  )
}

/** "Warm up first": one line at the top of a session until warmed up or dismissed. */
function WarmupNudge({ session, onChange }: { session: LiveSession; onChange: (s: LiveSession) => void }) {
  const [tick, setTick] = useState(() => Date.now())
  const started = session.cardioStartedAt ? new Date(session.cardioStartedAt).getTime() : null
  const left = started ? Math.max(0, CARDIO_MINUTES * 60 - Math.floor((tick - started) / 1000)) : null

  useEffect(() => {
    if (started == null) return
    const id = setInterval(() => setTick(Date.now()), 1000)
    return () => clearInterval(id)
  }, [started])

  useEffect(() => {
    if (left === 0) {
      navigator.vibrate?.([120, 60, 120])
      onChange(recordCardio(session, new Date()))
    }
  }, [left, session, onChange])

  return (
    <div className="flex min-h-12 items-center gap-1 rounded-2xl border border-highlight/40 bg-highlight-soft py-1 pr-1 pl-4 text-[15px]">
      {left == null ? (
        <>
          <span className="flex flex-1 flex-col">
            <span className="font-semibold">Warm Up First</span>
            <span>{CARDIO_MINUTES} min easy cardio</span>
          </span>
          <button type="button" onClick={() => onChange({ ...session, cardioStartedAt: new Date().toISOString() })}
            className={BTN.smallPrimary}>
            Start
          </button>
          <button type="button" aria-label="Skip the warm-up" onClick={() => onChange({ ...session, warmupNudge: 'skipped' })}
            className="flex size-10 items-center justify-center text-muted-foreground">
            <X size={18} aria-hidden />
          </button>
        </>
      ) : (
        <>
          <span className="flex-1 font-semibold">Easy cardio</span>
          <span aria-live="off" className="font-mono text-base font-semibold tabular-nums">
            {Math.floor(left / 60)}:{String(left % 60).padStart(2, '0')}
          </span>
          <button type="button" onClick={() => onChange(recordCardio(session, new Date()))}
            className={cn(BTN.smallPrimary, 'ml-2')}>
            Done
          </button>
        </>
      )}
    </div>
  )
}
