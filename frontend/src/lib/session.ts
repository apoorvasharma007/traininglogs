// The session in progress: how it starts, how it changes, and what is sent at Finish.
// Plain functions on plain data, so the screen stays thin and all of this is testable.
import { kg, sessionName } from '@/lib/format'
import type { SetDraft, SetKind } from '@/lib/review'
import { amountText, parseAmount } from '@/lib/movements'
import type { Movement, PlanExercise, SessionDetail, Workout } from '@/lib/types'

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
  planned?: boolean // one of the sets the workout's plan asked for, not one added today
}

export type LiveExercise = {
  key: string
  name: string
  choices: string[] // the plan line's exercise and its alternatives, suggested when renaming
  naming: boolean // a new exercise whose name is still being typed
  note: string // today's note
  noteOpen: boolean
  lastNote: string | null
  sets: LiveSet[]
  planIndex?: number // the workout plan line it started from; none when added during the session
}

/** A warm-up or cool-down movement in a session; left out at Finish unless ticked. */
export type LiveMovement = {
  key: string
  name: string
  amount: string
  done: boolean
  fromNudge?: boolean // recorded by "Warm up first", which every session offers anyway
  planIndex?: number // its place in the workout's planned warm-up or cool-down
}
export type MovementKind = 'warmup' | 'cooldown'

export type LiveSession = {
  clientId: string // the id the server uses to recognise a repeated send
  startedAt: string // ISO time
  date: string // YYYY-MM-DD, local
  programId: string | null
  workoutId: string | null
  title: string // the workout's name, or "Ad-hoc Workout"
  isDeload: boolean
  exercises: LiveExercise[]
  warmup?: LiveMovement[]
  cooldown?: LiveMovement[]
  // The "warm up first" prompt: dismissed or done for this session, and when its timer started.
  warmupNudge?: 'skipped' | 'done'
  cardioStartedAt?: string
  // Last time for each exercise and alternative in the plan, so switching refills from it.
  lasts?: LastExercise[]
}

export type LastSet = { weight_kg: number | null; reps: number | null; rpe?: number | null; notes: string | null }
export type LastExercise = { name: string; date: string; notes: string | null; warmup_sets: LastSet[]; sets: LastSet[] }

export type SessionRequest = {
  client_id: string
  date: string
  started_at: string
  ended_at: string
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
  warmup: { name: string; reps: number | null; duration_seconds: number | null; notes: string | null }[]
  cooldown: { name: string; reps: number | null; duration_seconds: number | null; notes: string | null }[]
}

/** 32 random hex characters. getRandomValues, unlike randomUUID, also works over plain http. */
function newKey(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, '0')).join('')
}

export function localDate(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** "120 × 2", "BW × 19", "80 × ?" */
function lastText(s: LastSet): string {
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
        planned: true,
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
    lasts,
    warmup: (workout.warmup ?? []).map((m, i) => ({ ...toLive(m), planIndex: i })),
    cooldown: (workout.cooldown ?? []).map((m, i) => ({ ...toLive(m), planIndex: i })),
    exercises: workout.exercises.map((plan, planIndex) => {
      const last = byName.get(nameKey(plan.name))
      return {
        key: newKey(),
        name: plan.name,
        choices: [plan.name, ...plan.alternatives],
        naming: false,
        note: '',
        noteOpen: false,
        lastNote: last?.notes ?? null,
        sets: plannedSets(plan, last),
        planIndex,
      }
    }),
  }
}

/** A session to do again: its exercises and set counts, its values in grey as "last time". */
export function startFromPast(past: SessionDetail, now: Date): LiveSession {
  const set = (kind: SetKind, weight: number | null, reps: number | null, last: string): LiveSet => ({
    ...blankSet(kind),
    weight: weight != null ? String(weight) : '',
    reps: reps != null ? String(reps) : '',
    ghost: true,
    last,
  })
  return {
    ...startBlank(now),
    title: sessionName(past),
    exercises: past.exercises.map((ex) => ({
      key: newKey(),
      name: ex.name,
      choices: [ex.name],
      naming: false,
      note: '',
      noteOpen: false,
      lastNote: ex.notes,
      sets: [
        ...ex.warmup_sets.map((w) => set('warmup', w.weight_kg, w.rep_count, lastText({ weight_kg: w.weight_kg, reps: w.rep_count, notes: null }))),
        ...ex.sets.map((w) => set('working', w.weight_kg, w.reps_full, lastText({ weight_kg: w.weight_kg, reps: w.reps_full, notes: null }))),
      ],
    })),
  }
}

const BLANK_TITLE = 'Ad-hoc Workout'

/** What a session is called on screen: an ad-hoc one takes its exercises' names once it has
 * some ("Squat, Bench Press and 1 more"), as History names it. */
export function liveTitle(s: LiveSession): string {
  const named = s.exercises.filter((e) => e.name.trim())
  return s.workoutId == null && s.title === BLANK_TITLE && named.length ? sessionName({ focus: null, exercises: named }) : s.title
}

export function startBlank(now: Date): LiveSession {
  return {
    clientId: newKey(),
    startedAt: now.toISOString(),
    date: localDate(now),
    programId: null,
    workoutId: null,
    title: BLANK_TITLE,
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
    exercises: s.exercises.map((e) => {
      const at = e.sets.findIndex((x) => x.key === setKey)
      if (at < 0) return e
      const kind = e.sets[at].kind
      return {
        ...e,
        sets: e.sets.map((x, i) => {
          if (i === at) return { ...x, [field]: value, ghost: false }
          // Cascade: the value shows in grey in the later sets of the same kind that nobody has
          // typed into or ticked yet, so typing a weight once covers every set.
          const untouched = x.ghost || (x.weight === '' && x.reps === '')
          if (i > at && value && x.kind === kind && !x.done && untouched) return { ...x, [field]: value, ghost: true }
          return x
        }),
      }
    }),
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
          ? {
              ...x, kind: draft.kind, weight: draft.weight, reps: draft.reps, rpe: draft.kind === 'working' ? draft.rpe : null, note: draft.note,
              // Weight and reps are typed on the row; the drawer leaves last time's suggestion as it is.
              ghost: x.ghost && draft.weight === x.weight && draft.reps === x.reps,
            }
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

export const MAX_RAMP = 10

/** Reps for a warm-up at this share of the working weight: fewer as it gets heavier. */
const rampReps = (pct: number) => (pct <= 60 ? 5 : pct <= 75 ? 3 : pct <= 85 ? 2 : 1)

/**
 * `count` warm-up sets (1 to 10) ramping up to `target` kg: spread evenly from 50% to 95% in
 * steps of 5%, so any count starts light and ends close to the working weight. Weights are
 * rounded to 2.5 kg.
 */
export function rampSets(target: number, count: number): { kg: number; reps: number }[] {
  if (!(count >= 1 && count <= MAX_RAMP)) return []
  return Array.from({ length: count }, (_, i) => {
    const pct = count === 1 ? 75 : 50 + Math.round((i * 45) / (count - 1) / 5) * 5
    return { kg: Math.round((target * pct) / 100 / 2.5) * 2.5, reps: rampReps(pct) }
  })
}

/** Adds warm-up sets after the exercise's warm-ups and before its working sets: a ramp's numbers in
 * grey to type over, or blank sets (null) to fill in. Sets already there stay as they are. */
export function addRamp(s: LiveSession, exKey: string, ramp: ({ kg: number; reps: number } | null)[]): LiveSession {
  return mapExercise(s, exKey, (e) => {
    const added = ramp.map((r) =>
      r ? { ...blankSet('warmup'), weight: String(r.kg), reps: String(r.reps), ghost: true } : blankSet('warmup'))
    const warm = e.sets.filter((x) => x.kind === 'warmup')
    return { ...e, sets: [...warm, ...added, ...e.sets.filter((x) => x.kind === 'working')] }
  })
}

/** Sets one set's effort, as RPE: asked right after a working set is ticked. */
export function setEffort(s: LiveSession, setKey: string, rpe: number): LiveSession {
  return {
    ...s,
    exercises: s.exercises.map((e) => ({ ...e, sets: e.sets.map((x) => (x.key === setKey ? { ...x, rpe } : x)) })),
  }
}

export function addExercise(s: LiveSession): { session: LiveSession; exKey: string } {
  const ex: LiveExercise = {
    key: newKey(), name: '', choices: [], naming: true, note: '', noteOpen: false, lastNote: null, sets: [blankSet('working')],
  }
  return { session: { ...s, exercises: [...s.exercises, ex] }, exKey: ex.key }
}

/**
 * Switches an exercise to one of its alternatives. Sets still showing last time's values are
 * refilled from the new exercise's last time; sets already ticked or typed into are kept.
 */
export function switchExercise(s: LiveSession, exKey: string, name: string): LiveSession {
  const last = s.lasts?.find((l) => nameKey(l.name) === nameKey(name))
  return mapExercise(s, exKey, (e) => {
    const counter = { warmup: 0, working: 0 }
    const sets = e.sets.map((x) => {
      const i = counter[x.kind]++
      const from = (x.kind === 'warmup' ? last?.warmup_sets : last?.sets) ?? []
      const source = from[i] ?? from[from.length - 1]
      const lastLabel = from[i] ? lastText(from[i]) : null
      if (x.done || !x.ghost) return { ...x, last: lastLabel }
      return {
        ...x,
        weight: source?.weight_kg != null ? String(source.weight_kg) : '',
        reps: source?.reps != null ? String(source.reps) : x.reps,
        last: lastLabel,
      }
    })
    return { ...e, name, lastNote: last?.notes ?? null, sets }
  })
}

/** Replaces an exercise's warmup sets with a ramp's, shown as suggestions until typed over or ticked. */
export function setWarmups(s: LiveSession, exKey: string, sets: { kg: number; reps: number }[]): LiveSession {
  // The new sets take the place of the planned ones they replace; any beyond that are extra.
  const planned = s.exercises.find((e) => e.key === exKey)?.sets.filter((x) => x.kind === 'warmup' && x.planned).length ?? 0
  return mapExercise(s, exKey, (e) => ({
    ...e,
    sets: [
      ...sets.map((w, i) => ({ ...blankSet('warmup'), weight: String(w.kg), reps: String(w.reps), ghost: true, planned: i < planned })),
      ...e.sets.filter((x) => x.kind === 'working'),
    ],
  }))
}

/** Moves an exercise one place up (-1) or down (1); at either end it stays put. */
export function moveExercise(s: LiveSession, exKey: string, by: -1 | 1): LiveSession {
  const i = s.exercises.findIndex((e) => e.key === exKey)
  const j = i + by
  if (i < 0 || j < 0 || j >= s.exercises.length) return s
  const exercises = [...s.exercises]
  ;[exercises[i], exercises[j]] = [exercises[j], exercises[i]]
  return { ...s, exercises }
}

export function removeExercise(s: LiveSession, exKey: string): LiveSession {
  return { ...s, exercises: s.exercises.filter((e) => e.key !== exKey) }
}

export function draftOf(set: LiveSet): SetDraft {
  return { kind: set.kind, weight: set.weight, reps: set.reps, rpe: set.rpe, note: set.note }
}

// ---- warm-up and cool-down ----

function toLive(m: Movement): LiveMovement {
  return { key: newKey(), name: m.name, amount: amountText(m), done: false }
}

function doneMovements(list: LiveMovement[] | undefined): SessionRequest['warmup'] {
  return (list ?? [])
    .filter((m) => m.done && m.name.trim())
    .map((m) => {
      const amount = parseAmount(m.amount)
      // An amount the rule can't read ("2 rounds", "each side 10") is kept as the note, not lost.
      const unread = m.amount.trim() && amount.reps == null && amount.duration_seconds == null ? m.amount.trim() : null
      return { name: m.name.trim(), ...amount, notes: unread }
    })
}

export function movementsOf(s: LiveSession, kind: MovementKind): LiveMovement[] {
  return s[kind] ?? []
}

export function setMovements(s: LiveSession, kind: MovementKind, list: LiveMovement[]): LiveSession {
  return { ...s, [kind]: list }
}

/** A preset's movements added after the ones already there. */
export function addPreset(s: LiveSession, kind: MovementKind, movements: Movement[]): LiveSession {
  return setMovements(s, kind, [...movementsOf(s, kind), ...movements.map(toLive)])
}

export function changeMovement(s: LiveSession, kind: MovementKind, key: string, patch: Partial<LiveMovement>): LiveSession {
  return setMovements(s, kind, movementsOf(s, kind).map((m) => (m.key === key ? { ...m, ...patch } : m)))
}

export const CARDIO_MINUTES = 5

/** Whether to show "warm up first": not dismissed, not done, and nothing in the warm-up ticked. */
export function wantsWarmupNudge(s: LiveSession): boolean {
  return s.warmupNudge == null && !movementsOf(s, 'warmup').some((m) => m.done)
}

/**
 * Records the easy cardio as done: the minutes since its timer started (at least 1, at most the
 * full time), or the full time when there was no timer. Ticks an existing "Easy cardio" row, or adds one.
 */
export function recordCardio(s: LiveSession, now: Date): LiveSession {
  const minutes = s.cardioStartedAt
    ? Math.min(CARDIO_MINUTES, Math.max(1, Math.round((now.getTime() - new Date(s.cardioStartedAt).getTime()) / 60000)))
    : CARDIO_MINUTES
  const list = movementsOf(s, 'warmup')
  const existing = list.find((m) => m.name.trim().toLowerCase() === 'easy cardio')
  const warmup = existing
    ? list.map((m) => (m === existing ? { ...m, amount: `${minutes} min`, done: true, fromNudge: true } : m))
    : [{ key: newKey(), name: 'Easy cardio', amount: `${minutes} min`, done: true, fromNudge: true }, ...list]
  return { ...s, warmup, warmupNudge: 'done', cardioStartedAt: undefined }
}

export function newMovement(): LiveMovement {
  return { key: newKey(), name: '', amount: '', done: false }
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
  // At least a minute: a session's duration has to be positive.
  const minutes = Math.max(1, Math.round((finishedAt.getTime() - new Date(s.startedAt).getTime()) / 60000))
  return {
    client_id: s.clientId,
    date: s.date,
    started_at: s.startedAt,
    ended_at: finishedAt.toISOString(),
    // A workout's session is named after it; History names any other by its exercises.
    focus: s.workoutId ? s.title : null,
    duration_minutes: minutes,
    program_workout_id: s.workoutId,
    is_deload: s.isDeload,
    warmup: doneMovements(s.warmup),
    cooldown: doneMovements(s.cooldown),
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

