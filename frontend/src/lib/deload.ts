// The deload reminder, remembered on this phone. It only reminds: OK hides it until another
// stretch of the program's deload weeks has passed. Deloading is the person's call.
import type { Program } from '@/lib/types'

const okKey = (id: string) => `tl_deload_ok_${id}`

function read(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

/** OK: no reminder for this program for another deload_after_days. */
export function acknowledgeDeload(p: Program, today: Date): void {
  const until = new Date(today)
  until.setDate(until.getDate() + p.deload_after_days)
  try {
    localStorage.setItem(okKey(p.id), until.toISOString())
  } catch {
    // Storage blocked: it shows again next time the app opens.
  }
}

export function showDeloadReminder(p: Program, today: Date): boolean {
  const until = read(okKey(p.id))
  return p.deload.due && !(until != null && new Date(until) > today)
}
