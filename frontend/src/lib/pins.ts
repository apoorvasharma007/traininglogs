// Notes pinned to an exercise, shown in every later session of it. Matched ignoring case.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'

type Pin = { name_key: string; note: string }

export const pinKey = (name: string) => name.trim().toLowerCase()

/** Pinned notes by exercise name key. */
export function usePins() {
  return useQuery({
    queryKey: ['pins'],
    queryFn: async () => new Map((await api<Pin[]>('/pins')).map((p) => [p.name_key, p.note])),
  })
}

export function usePinChange() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ name, note }: { name: string; note: string | null }) =>
      note == null
        ? api(`/pins/${encodeURIComponent(name)}`, { method: 'DELETE' })
        : api(`/pins/${encodeURIComponent(name)}`, { method: 'PUT', body: { note } }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['pins'] }),
  })
}
