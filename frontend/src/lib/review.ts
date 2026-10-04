// What the set editor on the Review screen sends to POST /extractions/{id}/edit.
// The sheet edits a local draft; on Done the draft is compared with the card's row and only the
// changed fields are sent, in one request.
import type { CardEdit, CardSetRow, CardWarmupRow } from '@/lib/types'

export type SetKind = 'warmup' | 'working'

export type SetDraft = {
  kind: SetKind
  weight: string // as typed; "" means none
  reps: string // "8", "8+1", "8L / 7R"; "" means none
  rpe: number | null
  note: string
}

export const RPES = [6, 6.5, 7, 7.5, 8, 8.5, 9, 9.5, 10]

// Placeholder name the server gives an added exercise (card_edits.NEW_EXERCISE_NAME).
export const NEW_EXERCISE_NAME = 'New exercise'

export function draftFromWarmup(row: CardWarmupRow): SetDraft {
  return {
    kind: 'warmup',
    weight: String(row.weight_kg ?? ''),
    reps: row.rep_count == null ? '' : String(row.rep_count),
    rpe: null,
    note: row.notes ?? '',
  }
}

export function draftFromSet(row: CardSetRow): SetDraft {
  return {
    kind: 'working',
    weight: row.weight_kg == null ? '' : String(row.weight_kg),
    reps: row.reps ?? '',
    rpe: row.rpe,
    note: row.notes ?? '',
  }
}

/** Weight after a ±2.5 tap: never below 0, no floating-point tails. */
export function stepWeight(weight: string, delta: number): string {
  const current = parseFloat(weight.replace(',', '.')) || 0
  return String(Math.max(0, Math.round((current + delta) * 10) / 10))
}

/** Reps after a ±1 tap. Only plain numbers step; "8+1" or "8L / 7R" are left to typing. */
export function stepReps(reps: string, delta: number): string | null {
  if (reps.trim() === '') return delta > 0 ? '1' : '0'
  if (!/^\d+$/.test(reps.trim())) return null
  return String(Math.max(0, Number(reps) + delta))
}

function numberOrEmpty(text: string): number | '' {
  const n = parseFloat(text.replace(',', '.'))
  return Number.isNaN(n) ? '' : n
}

/**
 * The card edits that turn `before` into `after` for the line at `path`. Kind changes are not
 * edits (the line moves to another list) and are handled by the caller.
 */
export function editsFor(path: string, before: SetDraft, after: SetDraft): CardEdit[] {
  const edits: CardEdit[] = []
  if (numberOrEmpty(after.weight) !== numberOrEmpty(before.weight)) {
    edits.push({ path, field: 'weight_kg', value: numberOrEmpty(after.weight) })
  }
  if (after.reps.trim() !== before.reps.trim()) {
    if (after.kind === 'warmup') {
      const n = parseInt(after.reps, 10)
      edits.push({ path, field: 'rep_count', value: Number.isNaN(n) ? '' : n })
    } else {
      edits.push({ path, field: 'reps', value: after.reps.trim() })
    }
  }
  if (after.kind === 'working' && after.rpe !== before.rpe) {
    edits.push({ path, field: 'rpe', value: after.rpe ?? '' })
  }
  if (after.note.trim() !== before.note.trim()) {
    edits.push({ path, field: 'notes', value: after.note.trim() })
  }
  return edits
}

/** The exercise path a set's path belongs to: "exercises.2.sets.1" -> "exercises.2". */
export function exercisePathOf(setPath: string): string {
  return setPath.split('.').slice(0, 2).join('.')
}
