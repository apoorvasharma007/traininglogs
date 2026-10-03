// The session in progress: how it starts, how it changes, and what is sent at Finish.
// Plain functions on plain data, so the screen stays thin and all of this is testable.
import { kg } from '@/lib/format'
import type { SetDraft, SetKind } from '@/lib/review'
import type { PlanExercise, Workout } from '@/lib/types'

export type LiveSet = {
  key: string
  kind: SetKind
  weight: string // "" when unknown
  reps: string // "" when unknown
  rpe: number | null
  note: string
  done: boolean
  // Values carried over from last time, shown grey until the set is edited or ticked.
  ghost: boolean
  last: string | null // "120 × 2", what this set was last time
}

export type LiveExercise = {
  key: string
  name: string
  naming: boolean // a new exercise whose name is still being typed
  note: string // today's note
  noteOpen: boolean
  lastNote: string | null
  sets: LiveSet[]
}

export type LiveSession = {
  clientId: string // the id the server uses to recognise a repeated send
  startedAt: string // ISO time
  date: string // YYYY-MM-DD, local
  programId: string | null
  workoutId: string | null
  title: string // "1 · Bench", or "Blank workout"
  isDeload: boolean
  exercises: LiveExercise[]
}

export type LastSet = { weight_kg: number | null; reps: number | null; rpe?: number | null; notes: string | null }
export type LastExercise = { name: string; date: string; notes: string | null; warmup_sets: LastSet[]; sets: LastSet[] }

export type SessionRequest = {
  client_id: string
  date: string
  focus: string | null
  duration_minutes: number
  program_workout_id: string | null
  is_deload: boolean
  exercises: {
    name: string
    notes: string | null
    warmup_sets: { weight_kg: number; reps: number | null; notes: string | null }[]
    sets: { weight_kg: number | null; reps: number | null; rpe: number | null; notes: string | null }[]
  }[]
}

/** 32 random hex characters. getRandomValues, unlike randomUUID, also works over plain http. */
export function newKey(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, '0')).join('')
}

export function localDate(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** "120 × 2", "BW × 19", "80 × ?" */
export function lastText(s: LastSet): string {
  return `${s.weight_kg ? kg(s.weight_kg) : 'BW'} × ${s.reps ?? '?'}`
}

const nameKey = (name: string) => name.trim().toLowerCase()

function blankSet(kind: SetKind): LiveSet {
  return { key: newKey(), kind, weight: '', reps: '', rpe: null, note: '', done: false, ghost: false, last: null }
}

/** Sets for one planned exercise: the plan's counts, filled from last time where it has a set. */
function plannedSets(plan: PlanExercise, last: LastExercise | undefined): LiveSet[] {
  const make = (kind: SetKind, count: number, from: LastSet[]): LiveSet[] =>
    Array.from({ length: count }, (_, i) => {
      // Extra planned sets repeat last time's final set: the usual "same again".
      const source = from[i] ?? from[from.length - 1]
      const reps = source?.reps ?? (kind === 'working' && !plan.amrap ? plan.target_reps : null)
      return {
        ...blankSet(kind),
        weight: source?.weight_kg != null ? String(source.weight_kg) : '',
        reps: reps != null ? String(reps) : '',
        ghost: source != null || reps != null,
        last: from[i] ? lastText(from[i]) : null,
      }
    })
  return [...make('warmup', plan.warmup_sets, last?.warmup_sets ?? []), ...make('working', plan.working_sets, last?.sets ?? [])]
}

export function startFromWorkout(
  workout: Workout,
  title: string,
  programId: string,
  lasts: LastExercise[],
  now: Date,
  isDeload = false,
): LiveSession {
  const byName = new Map(lasts.map((l) => [nameKey(l.name), l]))
  return {
    clientId: newKey(),
    startedAt: now.toISOString(),
    date: localDate(now),
    programId,
    workoutId: workout.id,
    title,
    isDeload,
    exercises: workout.exercises.map((plan) => {
      const last = byName.get(nameKey(plan.name))
      return {
        key: newKey(),
        name: plan.name,
        naming: false,
        note: '',
        noteOpen: false,
        lastNote: last?.notes ?? null,
        sets: plannedSets(plan, last),
      }
    }),
  }
}

export function startBlank(now: Date): LiveSession {
  return {
    clientId: newKey(),
    startedAt: now.toISOString(),
    date: localDate(now),
    programId: null,
    workoutId: null,
    title: 'Blank workout',
    isDeload: false,
    exercises: [],
  }
}

// ---- changes: each returns a new session, never edits the old one ----

function mapExercise(s: LiveSession, exKey: string, f: (e: LiveExercise) => LiveExercise): LiveSession {
  return { ...s, exercises: s.exercises.map((e) => (e.key === exKey ? f(e) : e)) }
}

export function updateExercise(s: LiveSession, exKey: string, patch: Partial<LiveExercise>): LiveSession {
  return mapExercise(s, exKey, (e) => ({ ...e, ...patch }))
}

export function toggleDone(s: LiveSession, setKey: string): LiveSession {
  return {
    ...s,
    exercises: s.exercises.map((e) => ({
      ...e,
      sets: e.sets.map((x) => (x.key === setKey ? { ...x, done: !x.done, ghost: false } : x)),
    })),
  }
}

/** A value typed into a set's weight or reps box. The set stops being last time's suggestion:
 * the other value stays, now as the person's own. */
export function setValue(s: LiveSession, setKey: string, field: 'weight' | 'reps', value: string): LiveSession {
  return {
    ...s,
    exercises: s.exercises.map((e) => ({
      ...e,
      sets: e.sets.map((x) => (x.key === setKey ? { ...x, [field]: value, ghost: false } : x)),
    })),
  }
}

/** Puts an edited set back, keeping warmup sets before working sets. */
export function saveSet(s: LiveSession, setKey: string, draft: SetDraft): LiveSession {
  return {
    ...s,
    exercises: s.exercises.map((e) => {
      if (!e.sets.some((x) => x.key === setKey)) return e
      const sets = e.sets.map((x) =>
        x.key === setKey
          ? { ...x, kind: draft.kind, weight: draft.weight, reps: draft.reps, rpe: draft.kind === 'working' ? draft.rpe : null, note: draft.note, ghost: false }
          : x,
      )
      return { ...e, sets: [...sets.filter((x) => x.kind === 'warmup'), ...sets.filter((x) => x.kind === 'working')] }
    }),
  }
}

export function removeSet(s: LiveSession, setKey: string): LiveSession {
  return { ...s, exercises: s.exercises.map((e) => ({ ...e, sets: e.sets.filter((x) => x.key !== setKey) })) }
}

/** "+ Set": copies the last working set's weight and reps, not yet done. */
export function addSet(s: LiveSession, exKey: string): { session: LiveSession; setKey: string } {
  const set = blankSet('working')
  const next = mapExercise(s, exKey, (e) => {
    const from = [...e.sets].reverse().find((x) => x.kind === 'working') ?? e.sets[e.sets.length - 1]
    return { ...e, sets: [...e.sets, { ...set, weight: from?.weight ?? '', reps: from?.reps ?? '', ghost: Boolean(from) }] }
  })
  return { session: next, setKey: set.key }
}

/** Adds a warmup set after the other warmups: the last warmup's weight, or half the first working
 * set rounded to 2.5 kg, or the empty bar. */
export function addWarmupSet(s: LiveSession, exKey: string): { session: LiveSession; setKey: string } {
  const set = blankSet('warmup')
  const next = mapExercise(s, exKey, (e) => {
    const warm = e.sets.filter((x) => x.kind === 'warmup')
    const first = parseFloat(e.sets.find((x) => x.kind === 'working')?.weight ?? '')
    const weight = warm.length
      ? warm[warm.length - 1].weight
      : String(first > 0 ? Math.max(20, Math.round((first * 0.5) / 2.5) * 2.5) : 20)
    const sets = [...warm, { ...set, weight, reps: '5' }, ...e.sets.filter((x) => x.kind === 'working')]
    return { ...e, sets }
  })
  return { session: next, setKey: set.key }
}

export function addExercise(s: LiveSession): { session: LiveSession; exKey: string } {
  const ex: LiveExercise = {
    key: newKey(), name: '', naming: true, note: '', noteOpen: false, lastNote: null, sets: [blankSet('working')],
  }
  return { session: { ...s, exercises: [...s.exercises, ex] }, exKey: ex.key }
}

export function removeExercise(s: LiveSession, exKey: string): LiveSession {
  return { ...s, exercises: s.exercises.filter((e) => e.key !== exKey) }
}

export function draftOf(set: LiveSet): SetDraft {
  return { kind: set.kind, weight: set.weight, reps: set.reps, rpe: set.rpe, note: set.note }
}

// ---- Finish ----

export function counts(s: LiveSession): { done: number; total: number } {
  const sets = s.exercises.flatMap((e) => e.sets)
  return { done: sets.filter((x) => x.done).length, total: sets.length }
}

const num = (text: string): number | null => {
  const n = parseFloat(text.replace(',', '.'))
  return Number.isNaN(n) ? null : n
}

/** What Finish sends: only ticked sets, and only exercises with at least one. */
export function toRequest(s: LiveSession, finishedAt: Date): SessionRequest {
  const minutes = Math.max(0, Math.round((finishedAt.getTime() - new Date(s.startedAt).getTime()) / 60000))
  return {
    client_id: s.clientId,
    date: s.date,
    focus: s.title,
    duration_minutes: minutes,
    program_workout_id: s.workoutId,
    is_deload: s.isDeload,
    exercises: s.exercises
      .map((e) => {
        const done = e.sets.filter((x) => x.done)
        return {
          name: e.name.trim(),
          notes: e.note.trim() || null,
          warmup_sets: done
            .filter((x) => x.kind === 'warmup')
            .map((x) => ({ weight_kg: num(x.weight) ?? 0, reps: num(x.reps), notes: x.note.trim() || null })),
          sets: done
            .filter((x) => x.kind === 'working')
            .map((x) => ({ weight_kg: num(x.weight), reps: num(x.reps), rpe: x.rpe, notes: x.note.trim() || null })),
        }
      })
      .filter((e) => e.name && (e.warmup_sets.length || e.sets.length)),
  }
}

/**
 * The workout's plan as this session actually went (exercises and how many sets of each kind),
 * or null when it matches the plan. Finish offers to update the workout with it.
 */
export function planFromSession(s: LiveSession, plan: PlanExercise[]): PlanExercise[] | null {
  const byName = new Map(plan.map((p) => [nameKey(p.name), p]))
  const next = s.exercises
    .filter((e) => e.name.trim())
    .map((e) => {
      const old = byName.get(nameKey(e.name))
      return {
        name: e.name.trim(),
        warmup_sets: e.sets.filter((x) => x.kind === 'warmup').length,
        working_sets: e.sets.filter((x) => x.kind === 'working').length,
        target_reps: old?.target_reps ?? null,
        amrap: old?.amrap ?? false,
      }
    })
  const same =
    next.length === plan.length &&
    next.every((p, i) => nameKey(p.name) === nameKey(plan[i].name) && p.warmup_sets === plan[i].warmup_sets && p.working_sets === plan[i].working_sets)
  return same ? null : next
}
