// Display rules for lifts on the Progress screens.
import { kg, parseDate } from '@/lib/format'
import type { LiftPoint, LiftSummary } from '@/lib/types'

/** "133.3 kg", or "19 reps" for a lift measured in reps at bodyweight. */
export function liftValue(l: { measure: LiftSummary['measure'] }, value: number): string {
  return l.measure === 'bodyweight_reps' ? `${value} reps` : `${kg(value)} kg`
}

/** "125 kg × 2 @ 9", or "BW × 19" for a bodyweight set. */
export function setText(set: LiftPoint['best_set']): string {
  const weight = set.weight_kg ? `${kg(set.weight_kg)} kg` : 'BW'
  return `${weight} × ${set.reps ?? '?'}${set.rpe != null ? ` @ ${set.rpe}` : ''}`
}

/** Points inside the last `days` days, counted back from the newest point. */
export function inRange<T extends { date: string }>(points: T[], days: number | null): T[] {
  if (days == null || points.length === 0) return points
  const newest = parseDate(points[points.length - 1].date).getTime()
  return points.filter((p) => newest - parseDate(p.date).getTime() <= days * 86_400_000)
}
