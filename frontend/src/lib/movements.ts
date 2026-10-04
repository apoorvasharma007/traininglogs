// Warm-up and cool-down movements for a whole session. An amount is typed as reps ("10") or a
// time ("3 min", "45 s"); empty means just do it ("easy walk").
import type { Movement } from '@/lib/types'

/** "10" -> 10 reps; "3 min", "3m" -> 180 s; "45 s", "45s" -> 45 s; anything else -> neither. */
export function parseAmount(text: string): { reps: number | null; duration_seconds: number | null } {
  const t = text.trim().toLowerCase()
  const time = t.match(/^(\d+(?:\.\d+)?)\s*(min|mins|m|s|sec|secs)$/)
  if (time) {
    const n = parseFloat(time[1])
    return { reps: null, duration_seconds: Math.round(time[2].startsWith('m') ? n * 60 : n) }
  }
  const reps = t.match(/^(?:x\s*)?(\d+)$/)
  return { reps: reps ? Number(reps[1]) : null, duration_seconds: null }
}

/** The amount as typed back: "10", "3 min", "45 s", or "". */
export function amountText(m: Pick<Movement, 'reps' | 'duration_seconds'>): string {
  if (m.duration_seconds != null) {
    return m.duration_seconds % 60 === 0 ? `${m.duration_seconds / 60} min` : `${m.duration_seconds} s`
  }
  return m.reps != null ? String(m.reps) : ''
}

const mv = (name: string, amount: string): Movement => ({ name, ...parseAmount(amount) })

export const WARMUP_PRESETS: { name: string; movements: Movement[] }[] = [
  { name: 'Easy cardio', movements: [mv('Easy cardio', '5 min')] },
  {
    name: 'Dynamic stretching',
    movements: [mv('Arm circles', ''), mv('Leg swings', ''), mv('Hip circles', ''), mv('Walking lunges', ''), mv('Torso twists', '')],
  },
]

export const COOLDOWN_PRESETS: { name: string; movements: Movement[] }[] = [
  { name: 'Easy cardio', movements: [mv('Easy cardio', '5 min')] },
  {
    name: 'Static stretching',
    movements: [mv('Hamstring stretch', ''), mv('Quad stretch', ''), mv('Chest stretch', ''), mv('Hip flexor stretch', '')],
  },
]
