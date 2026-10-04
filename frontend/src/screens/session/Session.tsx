import { useQueryClient } from '@tanstack/react-query'
import { Check, ChevronDown, X } from 'lucide-react'
import { MotionConfig } from 'motion/react'
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'wouter'
import ConfirmSheet from '@/components/ConfirmSheet'
import { Loading } from '@/components/QueryStatus'
import SetSheet, { type SetTarget } from '@/components/SetSheet'
import Sheet from '@/components/Sheet'
import { api } from '@/lib/api'
import { planChanges } from '@/lib/planChanges'
import { COOLDOWN_PRESETS, WARMUP_PRESETS } from '@/lib/movements'
import { WARMUPS, warmupSets } from '@/lib/warmup'
import {
  addExercise,
  addSet,
  addWarmupSet,
  counts,
  draftOf,
  moveExercise,
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
  type LiveSession,
} from '@/lib/session'
import { enqueue, flush, useLiveSession } from '@/lib/store'
import { setLastFinished } from '@/screens/session/finished'
import type { Program } from '@/lib/types'
import ExerciseCard from './ExerciseCard'
import MovementCard from './MovementCard'

function minutesSince(iso: string, now: number): number {
  return Math.max(0, Math.floor((now - new Date(iso).getTime()) / 60000))
}

/** The session in progress, full screen. Every change is saved on the phone straight away. */
export default function Session() {
  const { session, update } = useLiveSession()
  const [, navigate] = useLocation()
  const queryClient = useQueryClient()
  const [openSet, setOpenSet] = useState<SetTarget | null>(null)
  const [menuFor, setMenuFor] = useState<LiveExercise | null>(null)
  const [switchFor, setSwitchFor] = useState<LiveExercise | null>(null)
  const [warmupFor, setWarmupFor] = useState<LiveExercise | null>(null)
  // Finished exercises collapse; these were opened again by hand.
  const [reopened, setReopened] = useState<Set<string>>(() => new Set())
  const [undo, setUndo] = useState<{ text: string; before: LiveSession } | null>(null)
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
        <p className="font-semibold">No session in progress</p>
        <Link href="/" className="font-semibold text-muted-foreground underline">
          Back to Train
        </Link>
      </div>
    )
  }

  const s = session
  const { done, total } = counts(s)
  const finished = (e: LiveExercise) => e.sets.length > 0 && e.sets.every((x) => x.done)
  const current = s.exercises.find((e) => !finished(e))

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
    setUndo({ text, before: s })
  }

  function open(exKey: string, setKey: string, session: LiveSession = s) {
    const ex = session.exercises.find((e) => e.key === exKey)
    const index = ex?.sets.findIndex((x) => x.key === setKey) ?? -1
    if (!ex || index < 0) return
    const set = ex.sets[index]
    // Just the exercise: the Warm-up | Working switch already says which kind of set it is.
    setOpenSet({ key: setKey, title: ex.name || 'Exercise', draft: draftOf(set), last: set.last })
  }

  async function finish() {
    const finishedAt = new Date()
    const request = toRequest(s, finishedAt)
    if (request.exercises.length === 0) {
      setFinishError('Tick at least one set first. Unticked sets are not saved.')
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
      title: s.title,
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
        <header className="sticky top-0 z-10 -mx-4 mb-3 flex items-center gap-1 border-b border-border bg-background px-2 pt-3 pb-2">
          <Link href="/" aria-label="Minimise; the session keeps going" className="flex size-11 shrink-0 items-center justify-center">
            <ChevronDown size={22} aria-hidden />
          </Link>
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="truncate text-[17px] font-semibold">
              {s.title} <span className="font-normal text-muted-foreground">· {minutesSince(s.startedAt, now)} min</span>
            </span>
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <Check size={13} strokeWidth={2.6} aria-label="Saved on this phone" className="shrink-0 text-highlight" />
              <span className="truncate">
                {current ? <>Now: <span className="font-semibold text-foreground">{current.name || 'New exercise'}</span> · </> : 'All done · '}
                {done} of {total} sets
              </span>
            </span>
          </div>
          <button type="button" onClick={() => { setFinishError(null); setFinishing(true) }}
            className="h-10 shrink-0 rounded-xl bg-primary px-4 font-semibold text-primary-foreground transition active:scale-95">
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
              onTick={(set) => {
                if (!set.done) navigator.vibrate?.(10)
                const next = toggleDone(s, set.key)
                change(next)
                if (!set.done) {
                  setReopened((r) => { const n = new Set(r); n.delete(ex.key); return n })
                  scrollToNext(next, ex.key)
                }
              }}
              collapsed={finished(ex) && !reopened.has(ex.key)}
              onToggleCollapsed={() => setReopened((r) => {
                const n = new Set(r)
                if (n.has(ex.key)) n.delete(ex.key)
                else n.add(ex.key)
                return n
              })}
              onAddSet={() => change(addSet(s, ex.key).session)}
              onMenu={() => setMenuFor(ex)}
              onRename={(name) => change(updateExercise(s, ex.key, { name, naming: false }))}
              onSwitch={() => setSwitchFor(ex)}
              onNote={(note) => change(updateExercise(s, ex.key, { note }))}
            />
          ))}
          <button type="button" onClick={() => change(addExercise(s).session)}
            className="h-12 rounded-2xl border border-dashed border-muted-foreground/50 text-sm font-semibold text-muted-foreground transition active:scale-[0.98]">
            + Exercise
          </button>
          <MovementCard title="Cool-down" movements={movementsOf(s, 'cooldown')} presets={COOLDOWN_PRESETS}
            onChange={(list) => change(setMovements(s, 'cooldown', list))}
            onAddPreset={(m) => change(addPreset(s, 'cooldown', m))} />
        </div>

        {undo && (
          <div role="status" className="fixed inset-x-4 bottom-6 z-20 mx-auto flex max-w-md items-center justify-between gap-3 rounded-2xl bg-primary py-1.5 pr-1.5 pl-4 text-sm text-primary-foreground">
            <span>{undo.text}</span>
            <span className="flex">
              <button type="button" onClick={() => { update(undo.before); setUndo(null) }} className="h-10 px-3.5 font-bold text-highlight">
                Undo
              </button>
              <button type="button" aria-label="Dismiss" onClick={() => setUndo(null)} className="h-10 px-3 opacity-70">
                ✕
              </button>
            </span>
          </div>
        )}
      </div>

      <SetSheet target={openSet} busy={false} error={null}
        onClose={() => setOpenSet(null)}
        onDone={(draft) => { if (openSet) change(saveSet(s, openSet.key, draft)); setOpenSet(null) }}
        onDelete={() => { if (openSet) removeWithUndo(removeSet(s, openSet.key), 'Set removed'); setOpenSet(null) }} />

      <Sheet open={menuFor != null} onClose={() => setMenuFor(null)} label="Exercise options">
        {menuFor && (
          <>
            <span className="text-[17px] font-semibold">{menuFor.name || 'New exercise'}</span>
            <div className="flex flex-col overflow-hidden rounded-2xl border border-border">
              {[
                { label: 'Add warm-up set', run: () => { const r = addWarmupSet(s, menuFor.key); change(r.session); open(menuFor.key, r.setKey, r.session) } },
                { label: menuFor.note ? 'Edit note' : 'Add note', run: () => change(updateExercise(s, menuFor.key, { noteOpen: true })) },
                { label: 'Rename', run: () => change(updateExercise(s, menuFor.key, { naming: true })) },
                { label: 'Move up', run: () => change(moveExercise(s, menuFor.key, -1)) },
                { label: 'Move down', run: () => change(moveExercise(s, menuFor.key, 1)) },
                { label: 'Warm-up set templates', run: () => setWarmupFor(menuFor) },
                { label: 'Remove exercise', danger: true, run: () => removeWithUndo(removeExercise(s, menuFor.key), `${menuFor.name || 'Exercise'} removed`) },
              ].map((item) => (
                <button key={item.label} type="button" onClick={() => { setMenuFor(null); item.run() }}
                  className={`h-13 border-t border-border px-4 text-left text-[15px] font-medium first:border-t-0 ${item.danger ? 'text-destructive' : ''}`}>
                  {item.label}
                </button>
              ))}
            </div>
          </>
        )}
      </Sheet>

      <Sheet open={warmupFor != null} onClose={() => setWarmupFor(null)} label="Warm-up set templates">
        {warmupFor && <WarmupPicker exercise={warmupFor} onPick={(sets) => { change(setWarmups(s, warmupFor.key, sets)); setWarmupFor(null) }} />}
      </Sheet>

      <Sheet open={switchFor != null} onClose={() => setSwitchFor(null)} label="Switch exercise">
        {switchFor && (
          <>
            <div className="flex flex-col gap-1">
              <span className="text-[17px] font-semibold">Switch {switchFor.name}</span>
              <span className="text-sm text-muted-foreground">The program lists these as alternatives.</span>
            </div>
            <div className="flex flex-col overflow-hidden rounded-2xl border border-border">
              {switchFor.choices
                .filter((c) => c.trim().toLowerCase() !== switchFor.name.trim().toLowerCase())
                .map((c) => (
                  <button key={c} type="button"
                    onClick={() => { change(switchExercise(s, switchFor.key, c)); setSwitchFor(null) }}
                    className="h-13 border-t border-border px-4 text-left text-[15px] font-medium first:border-t-0">
                    {c}
                  </button>
                ))}
            </div>
          </>
        )}
      </Sheet>

      <Sheet open={finishing} onClose={() => setFinishing(false)} label="Finish session">
        <div className="flex flex-col gap-1.5">
          <span className="text-xl font-bold">Finish session?</span>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {done === total
              ? `All ${total} sets are ticked.`
              : `${done} of ${total} sets are ticked. The ${total - done} unticked are left out.`}{' '}
            It goes to your history now, or as soon as you're online.
          </p>
        </div>
        {finishError && <p role="alert" className="text-sm text-destructive">{finishError}</p>}
        <button type="button" onClick={finish}
          className="h-13 rounded-2xl bg-primary font-semibold text-primary-foreground transition active:scale-[0.98]">
          Save session
        </button>
        <button type="button" onClick={() => setFinishing(false)} className="h-12 rounded-2xl border border-border font-semibold">
          Keep going
        </button>
        <button type="button" onClick={() => { setFinishing(false); setDiscarding(true) }} className="h-10 text-sm font-semibold text-destructive">
          Discard session
        </button>
      </Sheet>

      <ConfirmSheet open={discarding} title="Discard this session?" body="Nothing from it is saved."
        confirmLabel="Discard session" onClose={() => setDiscarding(false)}
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
        <span className="text-[17px] font-semibold">Warm-up set templates</span>
        <span className="text-sm text-muted-foreground">
          {working > 0
            ? `Builds up to your first working set, ${working} kg.`
            : 'Add a weight to your first working set, and these build the warm-up sets up to it.'}
        </span>
      </div>
      {working > 0 && existing > 0 && (
        <span className="text-sm text-warning">Replaces the {existing} warm-up {existing === 1 ? 'set' : 'sets'} already here.</span>
      )}
      <div className="flex flex-col overflow-hidden rounded-2xl border border-border">
        {WARMUPS.map((w) => {
          // Without a working weight there's nothing to build toward: shown, but not tappable.
          const sets = working > 0 ? warmupSets(w.id, working) : []
          return (
            <button key={w.id} type="button" disabled={!(working > 0)} onClick={() => onPick(sets)}
              className="flex flex-col gap-1 border-t border-border px-4 py-3 text-left first:border-t-0 active:bg-muted disabled:opacity-40">
              <span className="text-[15px] font-semibold">{w.name}</span>
              {sets.length > 0 && (
                <span className="font-mono text-[13px] text-muted-foreground">{sets.map((x) => `${x.kg}×${x.reps}`).join(' · ')}</span>
              )}
            </button>
          )
        })}
      </div>
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
    <div className="flex min-h-12 items-center gap-1 rounded-2xl border border-highlight/40 bg-highlight-soft py-1 pr-1 pl-4 text-sm">
      {left == null ? (
        <>
          <span className="flex-1">
            <span className="font-semibold">Warm up first</span> · {CARDIO_MINUTES} min easy cardio
          </span>
          <button type="button" onClick={() => onChange({ ...session, cardioStartedAt: new Date().toISOString() })}
            className="h-10 rounded-xl bg-primary px-4 font-semibold text-primary-foreground">
            Start
          </button>
          <button type="button" aria-label="Skip the warm-up" onClick={() => onChange({ ...session, warmupNudge: 'skipped' })}
            className="flex size-10 items-center justify-center text-muted-foreground">
            <X size={16} aria-hidden />
          </button>
        </>
      ) : (
        <>
          <span className="flex-1 font-semibold">Easy cardio</span>
          <span aria-live="off" className="font-mono text-base font-semibold tabular-nums">
            {Math.floor(left / 60)}:{String(left % 60).padStart(2, '0')}
          </span>
          <button type="button" onClick={() => onChange(recordCardio(session, new Date()))}
            className="ml-2 h-10 rounded-xl bg-primary px-4 font-semibold text-primary-foreground">
            Done
          </button>
        </>
      )}
    </div>
  )
}
