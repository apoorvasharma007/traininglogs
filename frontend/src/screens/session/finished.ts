// What the Done screen shows about the session just finished. Kept in memory: it only needs to
// live from Finish to the Done screen.
import type { PlanExercise } from '@/lib/types'

export type Finished = {
  clientId: string
  title: string
  minutes: number
  sets: number
  programId: string | null
  workoutId: string | null
  newPlan: PlanExercise[] | null // the workout as it went, when that differs from its plan
}

let lastFinished: Finished | null = null

export function setLastFinished(f: Finished) {
  lastFinished = f
}

export function getLastFinished(): Finished | null {
  return lastFinished
}
