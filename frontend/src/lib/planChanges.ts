// How a session differed from its workout's plan, as a list of changes the person can save back
// to the program. Adding is easy (ticked by default); taking away or renaming is deliberate
// (unticked). Each exercise and movement is matched to the plan line it started from, never by
// name, so a typo can't reach the program unless it's ticked. Skipped sets are not changes, and
// weights and reps never go into a plan.
import { amountText, parseAmount } from '@/lib/movements'
import type { LiveMovement, LiveSession, LiveSet, MovementKind } from '@/lib/session'
import type { Movement, PlanExercise, Workout } from '@/lib/types'

export type PlanChange =
  | { id: string; type: 'sets'; index: number; warmup_sets: number; working_sets: number; label: string; on: boolean }
  | { id: string; type: 'rename'; index: number; name: string; label: string; on: false }
  | { id: string; type: 'main'; index: number; name: string; label: string; on: false }
  | { id: string; type: 'order'; order: number[]; label: string; on: false }
  | { id: string; type: 'remove'; index: number; label: string; on: false }
  | { id: string; type: 'add'; exercise: PlanExercise; label: string; on: true }
  | { id: string; type: 'movement'; kind: MovementKind; movement: Movement; label: string; on: true }
  | { id: string; type: 'movement-amount'; kind: MovementKind; index: number; movement: Movement; label: string; on: true }
  | { id: string; type: 'movement-remove'; kind: MovementKind; index: number; label: string; on: false }

/** Changes that take something out of the plan, shown in red. */
export const isRemoval = (c: PlanChange) => c.type === 'remove' || c.type === 'movement-remove'

const key = (name: string) => name.trim().toLowerCase()
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`
const KIND_LABEL: Record<MovementKind, string> = { warmup: 'Warm-up', cooldown: 'Cool-down' }

/** Sets that count toward the plan: the planned ones still there, plus extra ones that were done. */
const counted = (sets: LiveSet[], kind: LiveSet['kind']) =>
  sets.filter((x) => x.kind === kind && (x.planned || x.done)).length

export function planChanges(s: LiveSession, w: Workout): PlanChange[] {
  const changes: PlanChange[] = []
  const fromPlan = s.exercises.filter((e) => e.planIndex != null && w.exercises[e.planIndex])

  for (const ex of s.exercises) {
    const name = ex.name.trim()
    if (!name) continue
    const warmup = counted(ex.sets, 'warmup')
    const working = counted(ex.sets, 'working')
    const index = ex.planIndex
    const plan = index != null ? w.exercises[index] : undefined

    if (index == null || !plan) {
      // Added during the session: worth offering only if something of it was done.
      if (working + warmup === 0) continue
      changes.push({
        id: `add-${ex.key}`, type: 'add', on: true,
        label: `Add ${name} · ${plural(working, 'set', 'sets')}`,
        exercise: { name, warmup_sets: warmup, working_sets: working, target_reps: null, amrap: true, alternatives: [] },
      })
      continue
    }

    if (plan.alternatives.some((a) => key(a) === key(name))) {
      changes.push({ id: `main-${index}`, type: 'main', index, name, on: false, label: `Make ${name} the main exercise` })
    } else if (key(plan.name) !== key(name)) {
      changes.push({ id: `rename-${index}`, type: 'rename', index, name, on: false, label: `${plan.name} → ${name}` })
    }

    if (warmup !== plan.warmup_sets || working !== plan.working_sets) {
      const parts = [
        warmup !== plan.warmup_sets && `${plural(warmup, 'warm-up set', 'warm-up sets')} (was ${plan.warmup_sets})`,
        working !== plan.working_sets && `${plural(working, 'working set', 'working sets')} (was ${plan.working_sets})`,
      ].filter(Boolean)
      changes.push({
        id: `sets-${index}`, type: 'sets', index, warmup_sets: warmup, working_sets: working,
        label: `${plan.name}: ${parts.join(', ')}`,
        // Fewer sets means rows were deleted in the session: a removal, so it starts unticked.
        on: warmup >= plan.warmup_sets && working >= plan.working_sets,
      })
    }
  }

  // The workout's exercises in the order they were done. Exercises added during the session
  // don't count toward the order; they're offered as additions at the end.
  const order = fromPlan.map((e) => e.planIndex!)
  if (order.some((n, i) => i > 0 && n < order[i - 1])) {
    changes.push({
      id: 'order', type: 'order', order, on: false,
      label: `Change the order: ${order.map((i) => w.exercises[i].name).join(', ')}`,
    })
  }

  const present = new Set(order)
  w.exercises.forEach((p, index) => {
    if (!present.has(index)) changes.push({ id: `remove-${index}`, type: 'remove', index, label: `Remove ${p.name}`, on: false })
  })

  for (const kind of ['warmup', 'cooldown'] as const) changes.push(...movementChanges(kind, s[kind] ?? [], w[kind] ?? []))
  return changes
}

function movementChanges(kind: MovementKind, done: LiveMovement[], planned: Movement[]): PlanChange[] {
  const changes: PlanChange[] = []
  const label = KIND_LABEL[kind]
  planned.forEach((p, index) => {
    const m = done.find((x) => x.planIndex === index)
    if (!m?.done) {
      changes.push({ id: `${kind}-remove-${index}`, type: 'movement-remove', kind, index, on: false, label: `${label}: remove ${p.name}` })
      return
    }
    // "Warm up first" sets the cardio's time itself, so its amount isn't a plan change.
    const movement = { name: p.name, ...parseAmount(m.amount) }
    const was = amountText(p)
    const now = amountText(movement)
    if (!m.fromNudge && now && now !== was) {
      changes.push({
        id: `${kind}-amount-${index}`, type: 'movement-amount', kind, index, movement, on: true,
        label: `${p.name}: ${now}${was ? ` (was ${was})` : ''}`,
      })
    }
  })
  for (const m of done) {
    // "Warm up first" is offered every session, so its cardio isn't a change to the program.
    if (m.planIndex != null || !m.done || !m.name.trim() || m.fromNudge) continue
    const movement = { name: m.name.trim(), ...parseAmount(m.amount) }
    const amount = amountText(movement)
    changes.push({
      id: `${kind}-${m.key}`, type: 'movement', kind, movement, on: true,
      label: `${label}: add ${movement.name}${amount ? ` · ${amount}` : ''}`,
    })
  }
  return changes
}

/** The workout's new plan with the chosen changes applied, and which parts changed. */
export function applyChanges(w: Workout, changes: PlanChange[], chosen: Set<string>) {
  const picked = changes.filter((c) => chosen.has(c.id))
  const at = <T extends PlanChange['type']>(type: T, index: number) =>
    picked.find((c) => c.type === type && 'index' in c && c.index === index) as Extract<PlanChange, { type: T }> | undefined

  const exercises = w.exercises
    .map((p, i) => {
      const sets = at('sets', i)
      const rename = at('rename', i)
      const main = at('main', i)
      let line = sets ? { ...p, warmup_sets: sets.warmup_sets, working_sets: sets.working_sets } : p
      if (rename) line = { ...line, name: rename.name }
      if (main) line = { ...line, name: main.name, alternatives: [p.name, ...p.alternatives.filter((a) => key(a) !== key(main.name))] }
      return { line, i }
    })
  const order = picked.find((c) => c.type === 'order')
  // The exercises done in the session take their new order in the places they held; any not done
  // stay where they were.
  const ordered = order?.type === 'order' ? reorder(exercises, order.order) : exercises
  const kept = ordered
    .filter(({ i }) => !at('remove', i))
    .map(({ line }) => line)
    .concat(picked.flatMap((c) => (c.type === 'add' ? [c.exercise] : [])))

  const movements = (kind: MovementKind) => [
    ...(w[kind] ?? [])
      .map((m, i) => {
        const amount = picked.find((c) => c.type === 'movement-amount' && c.kind === kind && c.index === i)
        return amount?.type === 'movement-amount' ? amount.movement : m
      })
      .filter((_, i) => !picked.some((c) => c.type === 'movement-remove' && c.kind === kind && c.index === i)),
    ...picked.flatMap((c) => (c.type === 'movement' && c.kind === kind ? [c.movement] : [])),
  ]
  const isMovement = (c: PlanChange) => c.type.startsWith('movement')
  return {
    exercises: kept,
    warmup: movements('warmup'),
    cooldown: movements('cooldown'),
    exercisesChanged: picked.some((c) => !isMovement(c)),
    movementsChanged: picked.some(isMovement),
  }
}

function reorder<T extends { i: number }>(lines: T[], order: number[]): T[] {
  const slots = [...order].sort((a, b) => a - b)
  const result = [...lines]
  order.forEach((from, n) => {
    result[slots[n]] = lines[from]
  })
  return result
}
