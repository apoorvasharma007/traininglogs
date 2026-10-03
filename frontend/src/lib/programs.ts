// Programs and workouts: the API calls, the TanStack Query hooks around them, and how a workout
// is named and summarised on screen.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { PlanExercise, Program, Workout } from '@/lib/types'

/** "1 · Push", or "Workout 2" when it has no name. */
export function workoutTitle(w: Pick<Workout, 'position' | 'name'>): string {
  return w.name ? `${w.position} · ${w.name}` : `Workout ${w.position}`
}

/** "2 warmup · 3 × 2", "3 sets", "1 × max". */
export function planText(e: PlanExercise): string {
  const reps = e.amrap ? 'max' : e.target_reps
  const sets = reps != null ? `${e.working_sets} × ${reps}` : `${e.working_sets} ${e.working_sets === 1 ? 'set' : 'sets'}`
  return e.warmup_sets ? `${e.warmup_sets} warmup · ${sets}` : sets
}

export function usePrograms() {
  return useQuery({ queryKey: ['programs'], queryFn: () => api<Program[]>('/programs') })
}

export function useProgram(id: string) {
  return useQuery({ queryKey: ['program', id], queryFn: () => api<Program>(`/programs/${id}`) })
}

/**
 * A change to one program. The API answers with the whole program, which replaces what the
 * screen shows straight away; the programs list reloads in the background.
 */
export function useProgramChange(programId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (request: { path: string; method: string; body?: unknown }) =>
      api<Program>(request.path, { method: request.method, body: request.body }),
    onSuccess: (program) => {
      // Deleting answers with no body: forget the program instead of caching nothing.
      if (program) client.setQueryData(['program', programId], program)
      else client.removeQueries({ queryKey: ['program', programId] })
      client.invalidateQueries({ queryKey: ['programs'] })
    },
  })
}

export function useCreateProgram() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => api<Program>('/programs', { method: 'POST', body: { name } }),
    onSuccess: (program) => {
      client.setQueryData(['program', program.id], program)
      client.invalidateQueries({ queryKey: ['programs'] })
    },
  })
}
