// What the Done screen shows about the session just finished. Kept on the phone as well as in
// memory, so the screen, and its offer to update the program, survive the app being restarted
// on it. Cleared when the person leaves the Done screen.
import { del, get, set } from 'idb-keyval'
import type { PlanChange } from '@/lib/planChanges'
import type { Workout } from '@/lib/types'

export type Finished = {
  clientId: string
  title: string
  minutes: number
  sets: number
  programId: string | null
  workoutId: string | null
  // How the session differed from its workout, offered on the Done screen to save to the program.
  workout: Workout | null
  changes: PlanChange[]
  // The offer was answered (program updated, or kept as is), so it isn't asked again.
  answered?: boolean
}

const KEY = 'last-finished'
let lastFinished: Finished | null = null

export function setLastFinished(f: Finished): Promise<void> {
  lastFinished = f
  return set(KEY, f)
}

/** The summary in memory, if this run of the app finished the session. */
export function getLastFinished(): Finished | null {
  return lastFinished
}

/** The summary kept on the phone, after the app was restarted. */
export async function loadLastFinished(): Promise<Finished | null> {
  lastFinished = lastFinished ?? (await get<Finished>(KEY)) ?? null
  return lastFinished
}

export function clearLastFinished(): Promise<void> {
  lastFinished = null
  return del(KEY)
}
