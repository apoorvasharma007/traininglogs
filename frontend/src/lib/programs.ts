// Programs and workouts: the API calls, the TanStack Query hooks around them, and how a workout
// is named and summarised on screen.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { PlanExercise, Program, ProgramTemplate, Workout } from '@/lib/types'

/** A workout's name everywhere it's shown: the name it was given, or "Workout N" without one. */
export function workoutName(w: Pick<Workout, 'position' | 'name'>): string {
  const plain = `Workout ${w.position}`
  const name = w.name?.trim()
  // A name that only repeats the number reads as the plain one.
  return name && name.toLowerCase() !== plain.toLowerCase() ? name : plain
}

/** "or Bench press", "or Deadlift or Barbell Clean"; empty without alternatives. */
export function choicesText(e: PlanExercise): string {
  return e.alternatives.map((a) => `or ${a}`).join(' ')
}

/** "2 warm-up · 3 × 2", "3 sets", "1 × max". */
/** A planned exercise's working sets: "3 × 5", "1 × max", "3 sets". */
export function workingText(e: PlanExercise): string {
  const reps = e.amrap ? 'max' : e.target_reps
  return reps != null ? `${e.working_sets} × ${reps}` : `${e.working_sets} ${e.working_sets === 1 ? 'set' : 'sets'}`
}


export function usePrograms() {
  return useQuery({ queryKey: ['programs'], queryFn: () => api<Program[]>('/programs') })
}

export function useProgram(id: string) {
  const queryClient = useQueryClient()
  return useQuery({
    queryKey: ['program', id],
    queryFn: () => api<Program>(`/programs/${id}`),
    // Shown at once from the programs list Train already loaded, while the program itself loads.
    placeholderData: () => queryClient.getQueryData<Program[]>(['programs'])?.find((p) => p.id === id),
  })
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

export function useTemplates() {
  return useQuery({ queryKey: ['templates'], queryFn: () => api<ProgramTemplate[]>('/templates') })
}

/** Copies a template into your programs, answered with the new program. */
export function useCopyTemplate() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api<Program>(`/templates/${id}/copy`, { method: 'POST' }),
    onSuccess: (program) => {
      client.setQueryData(['program', program.id], program)
      client.invalidateQueries({ queryKey: ['programs'] })
    },
  })
}
