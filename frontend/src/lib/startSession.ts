// Starting a session: from a planned workout (with last time's values) or blank.
import { api } from '@/lib/api'
import { workoutTitle } from '@/lib/programs'
import { startBlank, startFromPast, startFromWorkout, type LastExercise, type LiveSession } from '@/lib/session'
import { loadSession, saveSession } from '@/lib/store'
import type { Program, SessionDetail, Workout } from '@/lib/types'

/** Last time for these exercises; empty when offline, so a session can still start. */
async function lastTimes(names: string[]): Promise<LastExercise[]> {
  if (names.length === 0) return []
  const query = names.map((n) => `name=${encodeURIComponent(n)}`).join('&')
  try {
    return await api<LastExercise[]>(`/exercises/last?${query}`)
  } catch {
    return []
  }
}

/**
 * Starts a session unless one is already in progress, which is kept: there is one session at a
 * time, and it is never thrown away without asking. Returns the session to open.
 */
export async function startSession(
  from: { program: Program; workout: Workout } | { past: SessionDetail } | 'blank',
): Promise<LiveSession> {
  const current = await loadSession()
  if (current) return current
  const now = new Date()
  const session =
    from === 'blank'
      ? startBlank(now)
      : 'past' in from
        ? startFromPast(from.past, now)
        : startFromWorkout(
          from.workout,
          workoutTitle(from.workout),
          from.program.id,
          await lastTimes(from.workout.exercises.flatMap((e) => [e.name, ...e.alternatives])),
          now,
        )
  await saveSession(session)
  return session
}
