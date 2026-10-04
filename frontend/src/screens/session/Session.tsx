import { useQueryClient } from '@tanstack/react-query'
import { Check, ChevronDown } from 'lucide-react'
import { MotionConfig } from 'motion/react'
import { useEffect, useState } from 'react'
import { Link, useLocation } from 'wouter'
import ConfirmSheet from '@/components/ConfirmSheet'
import { Loading } from '@/components/QueryStatus'
import SetSheet, { type SetTarget } from '@/components/SetSheet'
import Sheet from '@/components/Sheet'
import { pinKey, usePinChange, usePins } from '@/lib/pins'
import {
  addExercise,
  addSet,
  addWarmupSet,
  counts,
  draftOf,
  planFromSession,
  removeExercise,
  removeSet,
  saveSet,
  setValue,
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

function minutesSince(iso: string, now: number): number {
  return Math.max(0, Math.floor((now - new Date(iso).getTime()) / 60000))
}

/** The session in progress, full screen. Every change is saved on the phone straight away. */
export default function Session() {
  const { session, update } = useLiveSession()
  const [, navigate] = useLocation()
  const queryClient = useQueryClient()
  const pins = usePins()
  const pinChange = usePinChange()
  const [openSet, setOpenSet] = useState<SetTarget | null>(null)
  const [menuFor, setMenuFor] = useState<LiveExercise | null>(null)
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
    const n = ex.sets.slice(0, index + 1).filter((x) => x.kind === 'working').length
    setOpenSet({ key: setKey, title: `${ex.name || 'Exercise'} · ${set.kind === 'warmup' ? 'Warmup set' : `Set ${n}`}`, draft: draftOf(set) })
  }

  function finish() {
    const finishedAt = new Date()
    const request = toRequest(s, finishedAt)
    if (request.exercises.length === 0) {
      setFinishError('Tick at least one set first. Unticked sets are not saved.')
      return
    }
    const program = s.programId ? queryClient.getQueryData<Program>(['program', s.programId]) : undefined
    const plan = program?.workouts.find((w) => w.id === s.workoutId)?.exercises
    setLastFinished({
      clientId: s.clientId,
      title: s.title,
      minutes: request.duration_minutes,
      sets: request.exercises.reduce((n, e) => n + e.sets.length + e.warmup_sets.length, 0),
      programId: s.programId,
      workoutId: s.workoutId,
      newPlan: plan ? planFromSession(s, plan) : null,
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
              <Check size={13} strokeWidth={2.6} aria-hidden className="text-highlight" />
              {done} of {total} sets done · saved on this phone
            </span>
          </div>
          <button type="button" onClick={() => { setFinishError(null); setFinishing(true) }}
            className="h-10 shrink-0 rounded-xl bg-primary px-4 font-semibold text-primary-foreground transition active:scale-95">
            Finish
          </button>
        </header>

        {s.isDeload && (
          <p className="mb-3 rounded-xl bg-warning-soft px-3 py-2 text-sm text-warning">Deload: go lighter than last time.</p>
        )}

        <div className="flex flex-col gap-3">
          {s.exercises.map((ex) => (
            <ExerciseCard
              key={ex.key}
              exercise={ex}
              pinned={pins.data?.get(pinKey(ex.name)) ?? null}
              onOpenSet={(set) => open(ex.key, set.key)}
              onValue={(set, field, value) => change(setValue(s, set.key, field, value))}
              onTick={(set) => {
                if (!set.done) navigator.vibrate?.(10)
                change(toggleDone(s, set.key))
              }}
              onAddSet={() => change(addSet(s, ex.key).session)}
              onMenu={() => setMenuFor(ex)}
              onRename={(name) => change(updateExercise(s, ex.key, { name, naming: false }))}
              onNote={(note) => change(updateExercise(s, ex.key, { note }))}
              onTogglePin={() => {
                const pinned = pins.data?.get(pinKey(ex.name))
                const note = ex.note.trim()
                pinChange.mutate({ name: ex.name, note: pinned === note ? null : note })
              }}
            />
          ))}
          <button type="button" onClick={() => change(addExercise(s).session)}
            className="h-12 rounded-2xl border border-dashed border-muted-foreground/50 text-sm font-semibold text-muted-foreground transition active:scale-[0.98]">
            + Exercise
          </button>
          {pinChange.isError && <p role="alert" className="text-sm text-destructive">{pinChange.error.message}</p>}
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
                { label: 'Add warmup set', run: () => { const r = addWarmupSet(s, menuFor.key); change(r.session); open(menuFor.key, r.setKey, r.session) } },
                { label: 'Add set', run: () => { const r = addSet(s, menuFor.key); change(r.session); open(menuFor.key, r.setKey, r.session) } },
                { label: menuFor.note ? 'Edit note' : 'Add note', run: () => change(updateExercise(s, menuFor.key, { noteOpen: true })) },
                { label: 'Rename', run: () => change(updateExercise(s, menuFor.key, { naming: true })) },
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
