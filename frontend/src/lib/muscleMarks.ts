import { MUSCLE_GROUPS } from '@/lib/lists'

/** What a tap marks a muscle as. A muscle is primary or secondary, never both. */
export type MarkMode = 'primary' | 'secondary'

// Serratus has no shape of its own: it lies on the sides of the ribs, which the figure draws as Core.
const SHOWN_WITH: Record<string, string[]> = { Core: ['Serratus'] }

export const musclesOf = (group: string) => [...MUSCLE_GROUPS.find(([g]) => g === group)![1], ...(SHOWN_WITH[group] ?? [])]

/** Marks a muscle in this mode, moving it out of the other one; a muscle already marked in this mode is cleared. */
export function mark(primary: string[], secondary: string[], muscle: string, mode: MarkMode): [string[], string[]] {
  const p = primary.filter((m) => m !== muscle), s = secondary.filter((m) => m !== muscle)
  if (!(mode === 'primary' ? primary : secondary).includes(muscle)) (mode === 'primary' ? p : s).push(muscle)
  return [p, s]
}

/** The strongest mark among these muscles, or null when none is marked. */
export const markOf = (primary: string[], secondary: string[], muscles: string[]): MarkMode | null =>
  muscles.some((m) => primary.includes(m)) ? 'primary' : muscles.some((m) => secondary.includes(m)) ? 'secondary' : null

// Groups whose muscles all do one job, so a tap marks them all; the others mix jobs (front and rear
// delts, adductors and abductors), so a tap asks which.
const WHOLE_GROUPS = new Set(['Chest', 'Biceps', 'Triceps', 'Quads', 'Calves', 'Glutes', 'Lower Back'])

/** A tap on a group's shape: a whole group with nothing marked yet gets every muscle marked in this
 *  mode; anything else is left for the person to pick. */
export function tapGroup(primary: string[], secondary: string[], group: string, mode: MarkMode): [string[], string[]] {
  const muscles = MUSCLE_GROUPS.find(([g]) => g === group)![1]
  if (!WHOLE_GROUPS.has(group) || markOf(primary, secondary, muscles)) return [primary, secondary]
  return muscles.reduce<[string[], string[]]>(([p, s], m) => mark(p, s, m, mode), [primary, secondary])
}
