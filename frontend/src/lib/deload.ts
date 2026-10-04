// The deload reminder's two choices, remembered on this phone: "Start" (the next pass through
// the program is a deload) and "remind me in 7 days". The count itself comes from the server.
import type { Program } from '@/lib/types'

const startKey = (id: string) => `tl_deload_start_${id}`
const snoozeKey = (id: string) => `tl_deload_snooze_${id}`

function read(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function write(key: string, value: string | null) {
  try {
    if (value == null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch {
    // Storage blocked: the choice lasts until the page closes.
  }
}

export function startDeload(p: Program) {
  write(startKey(p.id), '1')
}

export function snoozeDeload(p: Program, today: Date) {
  const until = new Date(today)
  until.setDate(until.getDate() + 7)
  write(snoozeKey(p.id), until.toISOString())
}

/** What the home screen shows about deloading this program. */
export function deloadView(p: Program, today: Date): { remind: boolean; next: number | null; of: number } {
  const total = p.workouts.length
  const started = read(startKey(p.id)) != null
  const { in_progress: done, due } = p.deload
  // Once a deload session is saved, the server's count takes over from "Start".
  if (done > 0) write(startKey(p.id), null)
  const underWay = (done > 0 && done < total) || (started && done === 0)
  const snoozedUntil = read(snoozeKey(p.id))
  const snoozed = snoozedUntil != null && new Date(snoozedUntil) > today
  return { remind: due && !underWay && !snoozed, next: underWay ? done + 1 : null, of: total }
}
